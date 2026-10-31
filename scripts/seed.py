"""Наповнення БД демо-даними (MAINT-001): кімнати, демо-акаунти, демо-токени, дві ігри та один запис.

Запуск: ``python scripts/seed.py`` (також викликається під час старту сервера).

Скрипт ідемпотентний по кожній сутності окремо: кожна кімната, користувач і токен додаються,
лише якщо їх ще немає, тому його безпечно запускати на порожній, частково заповненій чи вже готовій БД.
Демо-ігри додаються лише в порожню таблицю ігор і лише тоді, коли існують їхні майстер і кімната
(зовнішні ключі не порушуються). Сіль паролів і демо-токени беруться зі змінних середовища
(PASSWORD_SALT, MASTER_TOKEN, PLAYER_TOKEN, OWNER_TOKEN), а не зі сталих у коді.
"""

import os
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "api"))

import db  # noqa: E402
import store  # noqa: E402
from models import Enrollment, Game, Room, Token, User  # noqa: E402

# (id, назва, місткість)
DEMO_ROOMS = [
    ("room_1", "Зала «Дракон»", 8),
    ("room_2", "Зала «Лабіринт»", 6),
    ("room_3", "Кімната «Таверна»", 5),
]

# (id, пошта, пароль, ім'я, роль, змінна середовища з токеном, токен за замовчуванням)
DEMO_USERS = [
    ("user_1", "master@club.test", "master-pass-1", "Андрій", "master", "MASTER_TOKEN", "master-token"),
    ("user_2", "player@club.test", "player-pass-1", "Марія", "player", "PLAYER_TOKEN", "player-token"),
    ("user_3", "owner@club.test", "owner-pass-1", "Олена", "owner", "OWNER_TOKEN", "owner-token"),
]


def _demo_games(now: datetime):
    # (id, майстер, кімната, назва, система, початок, тривалість, місць)
    return [
        ("game_1", "user_1", "room_1", "Прокляття Страда", "D&D 5e", now + timedelta(hours=2), 180, 5),
        (
            "game_2",
            "user_1",
            "room_2",
            "Поклик Ктулху: Маскарад",
            "Call of Cthulhu",
            now + timedelta(days=1, hours=1),
            240,
            4,
        ),
    ]


def seed_db() -> Dict[str, int]:
    """Створює відсутні демо-дані. Повертає, скільки записів кожного виду додано."""
    db.init_db()
    created = {"rooms": 0, "users": 0, "tokens": 0, "games": 0, "enrollments": 0}
    now = datetime.now(timezone.utc)

    with db.session_scope() as session:
        for room_id, name, capacity in DEMO_ROOMS:
            if session.get(Room, room_id) is None:
                session.add(Room(id=room_id, name=name, capacity=capacity, is_blocked=False))
                created["rooms"] += 1

        for user_id, email, password, name, role, _token_env, _token_default in DEMO_USERS:
            email_taken = session.query(User).filter(User.email == email).first() is not None
            if session.get(User, user_id) is None and not email_taken:
                session.add(
                    User(id=user_id, email=email, password_hash=store.hash_password(password), name=name, role=role)
                )
                created["users"] += 1
        session.flush()

        for user_id, _email, _password, _name, _role, token_env, token_default in DEMO_USERS:
            user = session.get(User, user_id)
            token_id = os.getenv(token_env, token_default)
            if user is not None and not user.is_blocked and session.get(Token, token_id) is None:
                session.add(Token(id=token_id, user_id=user_id))
                created["tokens"] += 1
        session.flush()

        if session.query(Game).count() == 0:
            for game_id, master_id, room_id, title, system, starts_at, minutes, max_players in _demo_games(now):
                if session.get(User, master_id) is None or session.get(Room, room_id) is None:
                    continue
                session.add(
                    Game(
                        id=game_id,
                        master_id=master_id,
                        room_id=room_id,
                        title=title,
                        system=system,
                        starts_at=starts_at,
                        duration_minutes=minutes,
                        max_players=max_players,
                    )
                )
                created["games"] += 1
                if game_id == "game_1" and session.get(User, "user_2") is not None:
                    session.add(Enrollment(game_id=game_id, player_id="user_2", enrolled_at=now))
                    created["enrollments"] += 1

    return created


if __name__ == "__main__":
    summary = seed_db()
    print(f"Базу даних заповнено демо-даними: {summary}")
