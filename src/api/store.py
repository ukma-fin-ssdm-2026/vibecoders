import hashlib
import hmac
import itertools
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from schemas import Game, GameBase, Player, Room, User, UserRole


class GameRecord(GameBase):
    id: str
    master_id: str


USERS: Dict[str, User] = {
    "user_1": User(id="user_1", name="Андрій", role=UserRole.master),
    "user_2": User(id="user_2", name="Марія", role=UserRole.player),
    "user_3": User(id="user_3", name="Олена", role=UserRole.owner),
}

TOKENS: Dict[str, str] = {
    "master-token": "user_1",
    "player-token": "user_2",
    "owner-token": "user_3",
}

# Replace Inline Code with Function Call:
# Сіль і токени беруться зі змінних середовища (закриває вразливість із static-analysis.md)
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "default-insecure-salt-for-dev").encode("utf-8")


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), PASSWORD_SALT, 100_000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


CREDENTIALS: Dict[str, Dict[str, str]] = {
    "master@club.test": {
        "user_id": "user_1",
        "password_hash": hash_password("master-pass-1"),
    },
    "player@club.test": {
        "user_id": "user_2",
        "password_hash": hash_password("player-pass-1"),
    },
    "owner@club.test": {
        "user_id": "user_3",
        "password_hash": hash_password("owner-pass-1"),
    },
}

USER_TOKENS: Dict[str, str] = {user_id: token for token, user_id in TOKENS.items()}

MAX_FAILED_LOGINS = 5
LOGIN_WINDOW = timedelta(minutes=15)
LOCK_DURATION = timedelta(minutes=15)
LOGIN_FAILURES: Dict[str, List[datetime]] = {}
LOCKED_UNTIL: Dict[str, datetime] = {}

ROOMS: Dict[str, Room] = {
    "room_1": Room(id="room_1", name="Зала «Дракон»", capacity=8, is_blocked=False),
    "room_2": Room(id="room_2", name="Зала «Лабіринт»", capacity=6, is_blocked=False),
    "room_3": Room(id="room_3", name="Кімната «Таверна»", capacity=5, is_blocked=False),
}

GAMES: Dict[str, GameRecord] = {
    "game_1": GameRecord(
        id="game_1",
        title="Прокляття Страда",
        system="D&D 5e",
        room_id="room_1",
        starts_at=datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc),
        duration_minutes=180,
        max_players=5,
        master_id="user_1",
    ),
    "game_2": GameRecord(
        id="game_2",
        title="Поклик Ктулху: Маскарад",
        system="Call of Cthulhu",
        room_id="room_2",
        starts_at=datetime(2026, 10, 11, 16, 0, tzinfo=timezone.utc),
        duration_minutes=240,
        max_players=4,
        master_id="user_1",
    ),
}

ENROLLMENTS: Dict[str, List[Player]] = {
    "game_1": [
        Player(
            user_id="user_2",
            name="Марія",
            enrolled_at=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc),
        )
    ],
    "game_2": [],
}

_game_sequence = itertools.count(3)


def next_game_id() -> str:
    return f"game_{next(_game_sequence)}"


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


def next_free_start(room_id: str, desired_start: datetime, duration_minutes: int) -> datetime:
    start = desired_start
    while busy := find_busy_game(start, duration_minutes, room_id=room_id):
        start = game_end(busy)
    return start
