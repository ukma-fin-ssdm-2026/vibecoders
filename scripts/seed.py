import os
import sys
from pathlib import Path

# Додаємо src/api до шляху для імпортів
sys.path.append(str(Path(__file__).resolve().parent.parent / "src" / "api"))

from db import SessionLocal, init_db  # noqa: E402
from models import Room, Token, User  # noqa: E402
import store  # noqa: E402


def seed_db():
    init_db()
    db = SessionLocal()
    try:
        # Створення кімнат (MAINT-001)
        if not db.query(Room).first():
            rooms = [
                Room(id="room_1", name="Зала «Дракон»", capacity=8, is_blocked=False),
                Room(id="room_2", name="Зала «Лабіринт»", capacity=6, is_blocked=False),
                Room(id="room_3", name="Кімната «Таверна»", capacity=5, is_blocked=False),
            ]
            db.add_all(rooms)

        # Створення демо-користувачів
        if not db.query(User).first():
            users = [
                User(
                    id="user_1",
                    email="master@club.test",
                    password_hash=store.hash_password("master-pass-1"),
                    name="Андрій",
                    role="master",
                ),
                User(
                    id="user_2",
                    email="player@club.test",
                    password_hash=store.hash_password("player-pass-1"),
                    name="Марія",
                    role="player",
                ),
                User(
                    id="user_3",
                    email="owner@club.test",
                    password_hash=store.hash_password("owner-pass-1"),
                    name="Олена",
                    role="owner",
                ),
            ]
            db.add_all(users)

            # Створення демо-токенів
            tokens = [
                Token(id=os.getenv("MASTER_TOKEN", "master-token"), user_id="user_1"),
                Token(id=os.getenv("PLAYER_TOKEN", "player-token"), user_id="user_2"),
                Token(id=os.getenv("OWNER_TOKEN", "owner-token"), user_id="user_3"),
            ]
            db.add_all(tokens)

        db.commit()
        print("Базу даних успішно заповнено демо-даними!")
    except Exception as e:
        db.rollback()
        print(f"Помилка під час наповнення БД: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
