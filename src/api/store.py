import hashlib
import hmac
import itertools
import logging
import os
import secrets
import threading
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from resilience import is_transient_db_error, retry_with_backoff

from schemas import Game, GameBase, Player, Room, User
from db import SessionLocal
from notifications import build_cancellation_rows
from models import (
    User as UserModel,
    Room as RoomModel,
    Game as GameModel,
    Enrollment as EnrollmentModel,
    Token as TokenModel,
    RoomBlock as RoomBlockModel,
    LoginFailure as LoginFailureModel,
)

logger = logging.getLogger("api.store")

db_lock = threading.RLock()


# Сіль береться зі змінних середовища (закриває вразливість із static-analysis.md)
def _load_password_salt() -> bytes:
    configured_salt = os.getenv("PASSWORD_SALT")
    if configured_salt and configured_salt.strip():
        return configured_salt.encode("utf-8")
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise RuntimeError("PASSWORD_SALT must be configured in production")
    logger.warning("PASSWORD_SALT is not set; using the insecure development salt")
    return b"default-insecure-salt-for-dev"


PASSWORD_SALT = _load_password_salt()


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), PASSWORD_SALT, 100_000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


MAX_FAILED_LOGINS = 5
LOGIN_WINDOW = timedelta(minutes=15)
LOCK_DURATION = timedelta(minutes=15)


def _naive_utc(value: datetime) -> datetime:
    """У БД час зберігається як наївний UTC."""
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class LoginFailuresProxy:
    """Невдалі входи за останні LOGIN_WINDOW. Стан у БД (R-09): переживає перезапуск і спільний для воркерів."""

    def get(self, email: str, default=None):
        db = SessionLocal()
        try:
            rows = (
                db.query(LoginFailureModel.failed_at)
                .filter(LoginFailureModel.email == email)
                .order_by(LoginFailureModel.failed_at, LoginFailureModel.id)
                .all()
            )
            return [failed_at.replace(tzinfo=timezone.utc) for (failed_at,) in rows] if rows else default
        finally:
            db.close()

    def pop(self, email: str, default=None):
        with db_lock:
            val = self.get(email)
            if val is None:
                return default  # нічого видаляти: успішний вхід без невдач не пише в БД
            db = SessionLocal()
            try:
                db.query(LoginFailureModel).filter(LoginFailureModel.email == email).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
            return val

    def clear(self):
        with db_lock:
            db = SessionLocal()
            try:
                db.query(LoginFailureModel).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()


LOGIN_FAILURES = LoginFailuresProxy()


class LockedUntilProxy:
    def get(self, email: str, default=None):
        db = SessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.email == email).first()
            return user.locked_until.replace(tzinfo=timezone.utc) if user and user.locked_until else default
        finally:
            db.close()

    def __setitem__(self, email: str, value: datetime):
        db = SessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.email == email).first()
            if user:
                user.locked_until = value.replace(tzinfo=None) if value else None
                db.commit()
        finally:
            db.close()

    def __delitem__(self, email: str):
        self.__setitem__(email, None)

    def __contains__(self, email: str):
        return self.get(email) is not None

    def pop(self, email: str, default=None):
        val = self.get(email, default)
        self.__setitem__(email, None)
        return val

    def clear(self):
        db = SessionLocal()
        try:
            db.query(UserModel).update({UserModel.locked_until: None})
            db.commit()
        finally:
            db.close()


LOCKED_UNTIL = LockedUntilProxy()


def record_failed_login(email: str, now: datetime) -> bool:
    """Атомарно записує невдалий вхід і за досягнення MAX_FAILED_LOGINS блокує акаунт (R-09).

    Усе виконується під db_lock в одній транзакції: паралельні спроби не губляться, а збій БД відкочує запис
    і піднімається вище (швидка відмова: 503, а не мовчазно пропущена спроба). Повертає True, якщо акаунт заблоковано.
    """
    now_db = _naive_utc(now)
    window_start = now_db - LOGIN_WINDOW
    with db_lock:
        db = SessionLocal()
        try:
            # Прострочені спроби неважливі нікому, тож чистимо їх разом (таблиця не росте без меж).
            db.query(LoginFailureModel).filter(LoginFailureModel.failed_at <= window_start).delete(
                synchronize_session=False
            )
            db.add(LoginFailureModel(email=email, failed_at=now_db))
            db.flush()
            attempts = db.query(LoginFailureModel).filter(LoginFailureModel.email == email).count()
            locked = attempts >= MAX_FAILED_LOGINS
            if locked:
                user = db.query(UserModel).filter(UserModel.email == email).first()
                if user is not None:
                    user.locked_until = _naive_utc(now + LOCK_DURATION)
                db.query(LoginFailureModel).filter(LoginFailureModel.email == email).delete(synchronize_session=False)
                logger.warning("Login lockout triggered after %d failed attempts", attempts)
            db.commit()
            return locked
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class GameRecord(GameBase):
    id: str
    master_id: str


CACHE_MAX_ENTRIES = 1024


class BoundedCache:
    """Потокобезпечний LRU-кеш з жорсткою межею розміру (R-15): найдавніший запис витісняється першим."""

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.max_entries = max_entries
        self._data: "OrderedDict[Any, Any]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key, default=None):
        with self._lock:
            if key not in self._data:
                return default
            self._data.move_to_end(key)
            return self._data[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def pop(self, key, default=None):
        with self._lock:
            return self._data.pop(key, default)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __contains__(self, key):
        with self._lock:
            return key in self._data

    def __len__(self):
        with self._lock:
            return len(self._data)


class DBProxyDict:
    """Проксі над таблицею БД. Кеш лише зберігає ідентичність об'єктів (оператор is у тестах), а не дані (R-15):
    значення завжди перебудовується з рядка БД, і закешований об'єкт повертається, лише якщо він йому дорівнює.
    Тому застарілий запис неможливий і ручна інвалідація не потрібна; розмір кешу обмежено."""

    def __init__(self, model_class, schema_class=None, transform_func=None, max_cache_entries=CACHE_MAX_ENTRIES):
        self.model_class = model_class
        self.schema_class = schema_class
        self.transform_func = transform_func
        self._cache = BoundedCache(max_cache_entries)

    def _build(self, db_obj):
        if self.transform_func:
            return self.transform_func(db_obj)
        data = {col: getattr(db_obj, col) for col in db_obj.__table__.columns.keys()}
        return self.schema_class(**data) if self.schema_class else data

    def _to_schema(self, db_obj):
        fresh = self._build(db_obj)
        cached = self._cache.get(db_obj.id)
        if cached is not None and cached == fresh:
            return cached
        self._cache[db_obj.id] = fresh
        return fresh

    def invalidate(self, key):
        """Явно прибирає запис із кешу (єдина точка замість прямих звернень до _cache)."""
        self._cache.pop(key, None)

    def get(self, key, default=None):
        db = SessionLocal()
        try:
            obj = db.query(self.model_class).filter(self.model_class.id == key).first()
            return self._to_schema(obj) if obj else default
        finally:
            db.close()

    def __getitem__(self, key):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key, value):
        db = SessionLocal()
        try:
            obj = db.query(self.model_class).filter(self.model_class.id == key).first()
            if not obj:
                obj = self.model_class(id=key)
                db.add(obj)
            data = value.model_dump() if hasattr(value, "model_dump") else value
            for k, v in data.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            db.commit()
            self._cache[key] = value
        finally:
            db.close()

    def __delitem__(self, key):
        db = SessionLocal()
        try:
            obj = db.query(self.model_class).filter(self.model_class.id == key).first()
            if obj:
                db.delete(obj)
                db.commit()
                self.invalidate(key)
            else:
                raise KeyError(key)
        finally:
            db.close()

    def values(self):
        db = SessionLocal()
        try:
            objs = db.query(self.model_class).all()
            return [self._to_schema(obj) for obj in objs]
        finally:
            db.close()

    def items(self):
        db = SessionLocal()
        try:
            objs = db.query(self.model_class).all()
            return [(obj.id, self._to_schema(obj)) for obj in objs]
        finally:
            db.close()

    def __contains__(self, key):
        return self.get(key) is not None

    def __iter__(self):
        db = SessionLocal()
        try:
            return iter([obj.id for obj in db.query(self.model_class).all()])
        finally:
            db.close()

    def __len__(self):
        db = SessionLocal()
        try:
            return db.query(self.model_class).count()
        finally:
            db.close()


class AutoSaveList(list):
    """Список, який автоматично зберігає себе в БД при виклику append (запобігає втраті даних)."""

    def __init__(self, game_id, proxy, iterable=()):
        super().__init__(iterable)
        self.game_id = game_id
        self.proxy = proxy

    def append(self, item):
        super().append(item)
        self.proxy[self.game_id] = self

    def remove(self, item):
        super().remove(item)
        self.proxy[self.game_id] = self


class EnrollmentsProxy:
    def get(self, game_id, default=None):
        db = SessionLocal()
        try:
            enrollments = db.query(EnrollmentModel).filter(EnrollmentModel.game_id == game_id).all()
            if not enrollments and default is not None:
                return AutoSaveList(game_id, self, default)
            res = [
                Player(user_id=e.player_id, name=e.player.name, enrolled_at=e.enrolled_at.replace(tzinfo=timezone.utc))
                for e in enrollments
            ]
            return AutoSaveList(game_id, self, res)
        finally:
            db.close()

    def setdefault(self, game_id, default):
        return self.get(game_id, default)

    def pop(self, game_id, default=None):
        res = self.get(game_id, default)
        self.__setitem__(game_id, [])
        return res

    def __getitem__(self, game_id):
        return self.get(game_id, [])

    def __setitem__(self, game_id, players_list):
        db = SessionLocal()
        try:
            db.query(EnrollmentModel).filter(EnrollmentModel.game_id == game_id).delete()
            for player in players_list:
                db.add(EnrollmentModel(game_id=game_id, player_id=player.user_id, enrolled_at=player.enrolled_at))
            db.commit()
        finally:
            db.close()

    def __contains__(self, game_id):
        db = SessionLocal()
        try:
            return db.query(EnrollmentModel).filter(EnrollmentModel.game_id == game_id).count() > 0
        finally:
            db.close()


def _fetch_credentials(email: str):
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if user:
            return {"user_id": user.id, "password_hash": user.password_hash}
        return None
    finally:
        db.close()


class CredentialsProxy:
    def __init__(self):
        self._fetch_with_retry = retry_with_backoff(
            _fetch_credentials,
            max_attempts=3,
            base_delay=0.05,
            max_delay=0.5,
            retry_on=(OperationalError,),
            predicate=is_transient_db_error,
        )

    def get(self, email, default=None):
        res = self._fetch_with_retry(email)
        return res if res is not None else default

    def __getitem__(self, email):
        val = self.get(email)
        if val is None:
            raise KeyError(email)
        return val

    def values(self):
        db = SessionLocal()
        try:
            users = db.query(UserModel).all()
            return [{"user_id": u.id, "password_hash": u.password_hash} for u in users]
        finally:
            db.close()


class UserTokensProxy:
    def __getitem__(self, user_id):
        db = SessionLocal()
        try:
            token = db.query(TokenModel).filter(TokenModel.user_id == user_id).first()
            if token:
                return token.id
            raise KeyError(user_id)
        finally:
            db.close()


def is_user_blocked(user_id: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        return user is None or user.is_blocked
    finally:
        db.close()


def _numeric_id_suffix(identifier: str, prefix: str) -> Optional[int]:
    if not identifier.startswith(prefix):
        return None
    suffix = identifier[len(prefix) :]
    if not suffix.isascii() or not suffix.isdecimal():
        return None
    return int(suffix)


def create_registered_user(name: str, email: str, password: str):
    db = SessionLocal()
    try:
        if db.query(UserModel).filter(UserModel.email == email).first():
            return None
        existing_ids = db.query(UserModel.id).all()
        numbers = []
        for (user_id,) in existing_ids:
            number = _numeric_id_suffix(user_id, "user_")
            if number is not None:
                numbers.append(number)
        next_id = max(numbers, default=0) + 1
        user = UserModel(
            id=f"user_{next_id}",
            email=email,
            password_hash=hash_password(password),
            name=name,
            role="player",
        )
        token = TokenModel(id=secrets.token_urlsafe(32), user_id=user.id)
        db.add_all([user, token])
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if db.query(UserModel).filter(UserModel.email == email).first():
                return None
            raise
        return user.id, token.id
    finally:
        db.close()


def set_user_blocked(user_id: str, is_blocked: bool):
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if user is None:
            return None
        user.is_blocked = is_blocked
        if is_blocked:
            db.query(TokenModel).filter(TokenModel.user_id == user_id).delete()
        db.commit()
        return User(id=user.id, name=user.name, role=user.role), user.is_blocked
    finally:
        db.close()


def _game_transform(obj: GameModel) -> GameRecord:
    starts_at = obj.starts_at.replace(tzinfo=timezone.utc) if obj.starts_at.tzinfo is None else obj.starts_at
    return GameRecord(
        id=obj.id,
        master_id=obj.master_id,
        room_id=obj.room_id,
        title=obj.title,
        system=obj.system,
        starts_at=starts_at,
        duration_minutes=obj.duration_minutes,
        max_players=obj.max_players,
    )


def _token_transform(obj: TokenModel) -> str:
    return obj.user_id


USERS = DBProxyDict(UserModel, User)
TOKENS = DBProxyDict(TokenModel, transform_func=_token_transform)
USER_TOKENS = UserTokensProxy()
CREDENTIALS = CredentialsProxy()
ROOMS = DBProxyDict(RoomModel, Room)
GAMES = DBProxyDict(GameModel, transform_func=_game_transform)
ENROLLMENTS = EnrollmentsProxy()


_game_sequence = itertools.count(3)


def _highest_game_number() -> int:
    db = SessionLocal()
    try:
        game_ids = [game_id for (game_id,) in db.query(GameModel.id).all()]
    finally:
        db.close()
    numbers = []
    for game_id in game_ids:
        number = _numeric_id_suffix(game_id, "game_")
        if number is not None:
            numbers.append(number)
    return max(numbers, default=0)


def next_game_id() -> str:
    """Наступний id гри. Після перезапуску лічильник у пам'яті починається з початку,
    тому він завжди випереджає найбільший id, що вже збережений у БД (інакше нова гра перезаписала б стару)."""
    global _game_sequence
    number = next(_game_sequence)
    first_free = _highest_game_number() + 1
    if number < first_free:
        number = first_free
        _game_sequence = itertools.count(first_free + 1)
    return f"game_{number}"


def delete_game_with_notifications(game_id: str) -> None:
    db = SessionLocal()
    try:
        game = db.get(GameModel, game_id)
        if game is None:
            return
        player_ids = [
            player_id
            for (player_id,) in db.query(EnrollmentModel.player_id).filter(EnrollmentModel.game_id == game_id).all()
        ]
        db.add_all(build_cancellation_rows(game_id, game.title, player_ids))
        db.delete(game)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    GAMES.invalidate(game_id)


def to_game(record: GameRecord) -> Game:
    return Game(**record.model_dump(), current_players=len(ENROLLMENTS.get(record.id, [])))


def sorted_games(records: List[GameRecord]) -> List[GameRecord]:
    return sorted(records, key=lambda r: (r.starts_at, r.id))


def query_games(
    room_id: Optional[str] = None,
    master_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> Tuple[List[GameRecord], int]:
    """Сторінка ігор і загальна кількість; фільтр, порядок (starts_at, id) і зріз виконує БД (R-14)."""
    db = SessionLocal()
    try:
        query = db.query(GameModel)
        if room_id:
            query = query.filter(GameModel.room_id == room_id)
        if master_id:
            query = query.filter(GameModel.master_id == master_id)
        total = query.count()
        page = query.order_by(GameModel.starts_at, GameModel.id).offset(offset)
        if limit is not None:
            page = page.limit(limit)
        return [GAMES._to_schema(obj) for obj in page.all()], total
    finally:
        db.close()


def room_has_games(room_id: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(GameModel.id).filter(GameModel.room_id == room_id).first() is not None
    finally:
        db.close()


def time_overlap(start_a: datetime, minutes_a: int, start_b: datetime, minutes_b: int) -> bool:
    return start_a < start_b + timedelta(minutes=minutes_b) and start_b < start_a + timedelta(minutes=minutes_a)


def find_busy_game(
    starts_at: datetime,
    duration_minutes: int,
    room_id: Optional[str] = None,
    master_id: Optional[str] = None,
    exclude_game_id: Optional[str] = None,
) -> Optional[GameRecord]:
    conditions = []
    if room_id is not None:
        conditions.append(GameModel.room_id == room_id)
    if master_id is not None:
        conditions.append(GameModel.master_id == master_id)
    if not conditions:
        return None
    with db_lock:
        db = SessionLocal()
        try:
            # R-14: з БД беремо лише ігри цієї кімнати або цього майстра, а не всю таблицю.
            query = db.query(GameModel).filter(or_(*conditions))
            if exclude_game_id is not None:
                query = query.filter(GameModel.id != exclude_game_id)
            for obj in query.order_by(GameModel.starts_at, GameModel.id).all():
                record = GAMES._to_schema(obj)
                if time_overlap(starts_at, duration_minutes, record.starts_at, record.duration_minutes):
                    return record
            return None
        finally:
            db.close()


def game_end(record: GameRecord) -> datetime:
    return record.starts_at + timedelta(minutes=record.duration_minutes)


def find_room_block(room_id: str, starts_at: datetime, duration_minutes: int):
    start = starts_at.astimezone(timezone.utc).replace(tzinfo=None)
    end = start + timedelta(minutes=duration_minutes)
    db = SessionLocal()
    try:
        return (
            db.query(RoomBlockModel)
            .filter(
                RoomBlockModel.room_id == room_id,
                RoomBlockModel.starts_at < end,
                RoomBlockModel.ends_at > start,
            )
            .first()
        )
    finally:
        db.close()


def next_free_start(room_id: str, desired_start: datetime, duration_minutes: int) -> datetime:
    start = desired_start
    while busy := find_busy_game(start, duration_minutes, room_id=room_id):
        start = game_end(busy)
    return start
