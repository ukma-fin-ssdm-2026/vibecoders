import hashlib
import hmac
import os
import itertools
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from schemas import Game, GameBase, Player, Room, User
from db import SessionLocal
from models import (
    User as UserModel,
    Room as RoomModel,
    Game as GameModel,
    Enrollment as EnrollmentModel,
    Token as TokenModel,
    RoomBlock as RoomBlockModel,
)

db_lock = threading.RLock()

# Сіль береться зі змінних середовища (закриває вразливість із static-analysis.md)
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "default-insecure-salt-for-dev").encode("utf-8")


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), PASSWORD_SALT, 100_000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


MAX_FAILED_LOGINS = 5
LOGIN_WINDOW = timedelta(minutes=15)
LOCK_DURATION = timedelta(minutes=15)
LOGIN_FAILURES: Dict[str, List[datetime]] = {}


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


class GameRecord(GameBase):
    id: str
    master_id: str


class DBProxyDict:
    """Проксі-клас із внутрішнім кешем для збереження ідентичності об'єктів (оператор is у тестах)."""

    def __init__(self, model_class, schema_class=None, transform_func=None):
        self.model_class = model_class
        self.schema_class = schema_class
        self.transform_func = transform_func
        self._cache = {}

    def _to_schema(self, db_obj):
        if db_obj.id in self._cache:
            return self._cache[db_obj.id]
        if self.transform_func:
            res = self.transform_func(db_obj)
        else:
            data = {col: getattr(db_obj, col) for col in db_obj.__table__.columns.keys()}
            res = self.schema_class(**data) if self.schema_class else data
        self._cache[db_obj.id] = res
        return res

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
                self._cache.pop(key, None)
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


class CredentialsProxy:
    def get(self, email, default=None):
        db = SessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.email == email).first()
            if user:
                return {"user_id": user.id, "password_hash": user.password_hash}
            return default
        finally:
            db.close()

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


def create_registered_user(name: str, email: str, password: str):
    db = SessionLocal()
    try:
        if db.query(UserModel).filter(UserModel.email == email).first():
            return None
        existing_ids = db.query(UserModel.id).all()
        next_id = (
            max(
                (int(user_id.removeprefix("user_")) for (user_id,) in existing_ids if user_id.startswith("user_")),
                default=0,
            )
            + 1
        )
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
    numbers = [int(game_id[5:]) for game_id in game_ids if game_id.startswith("game_") and game_id[5:].isdigit()]
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


def to_game(record: GameRecord) -> Game:
    return Game(**record.model_dump(), current_players=len(ENROLLMENTS.get(record.id, [])))


def sorted_games(records: List[GameRecord]) -> List[GameRecord]:
    return sorted(records, key=lambda r: (r.starts_at, r.id))


def time_overlap(start_a: datetime, minutes_a: int, start_b: datetime, minutes_b: int) -> bool:
    return start_a < start_b + timedelta(minutes=minutes_b) and start_b < start_a + timedelta(minutes=minutes_a)


def find_busy_game(
    starts_at: datetime,
    duration_minutes: int,
    room_id: Optional[str] = None,
    master_id: Optional[str] = None,
    exclude_game_id: Optional[str] = None,
) -> Optional[GameRecord]:
    with db_lock:
        for record in sorted_games(list(GAMES.values())):
            if record.id == exclude_game_id:
                continue
            same_room = room_id is not None and record.room_id == room_id
            same_master = master_id is not None and record.master_id == master_id
            if (same_room or same_master) and time_overlap(
                starts_at, duration_minutes, record.starts_at, record.duration_minutes
            ):
                return record
        return None


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
