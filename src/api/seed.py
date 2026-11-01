import os
from datetime import datetime, timedelta, timezone

from db import SessionLocal, init_db
from models import Enrollment, Game, Room, Token, User
import store


def seed_db() -> None:
    init_db()
    db = SessionLocal()
    try:
        rooms = [
            Room(id="room_1", name="Зала «Дракон»", capacity=8, is_blocked=False),
            Room(id="room_2", name="Зала «Лабіринт»", capacity=6, is_blocked=False),
            Room(id="room_3", name="Кімната «Таверна»", capacity=5, is_blocked=False),
        ]
        for room in rooms:
            if db.get(Room, room.id) is None:
                db.add(room)

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
        for user in users:
            if db.get(User, user.id) is None:
                existing_email = db.query(User.id).filter(User.email == user.email).first()
                if existing_email is not None:
                    raise ValueError(f"Демо-пошта {user.email} вже прив'язана до іншого користувача")
                db.add(user)

        tokens = [
            (os.getenv("MASTER_TOKEN", "master-token"), "user_1"),
            (os.getenv("PLAYER_TOKEN", "player-token"), "user_2"),
            (os.getenv("OWNER_TOKEN", "owner-token"), "user_3"),
        ]
        for token_id, user_id in tokens:
            existing_token = db.get(Token, token_id)
            if existing_token is None:
                db.add(Token(id=token_id, user_id=user_id))
            elif existing_token.user_id != user_id:
                raise ValueError(f"Токен {token_id} вже прив'язаний до іншого користувача")

        now = datetime.now(timezone.utc)
        games = [
            Game(
                id="game_1",
                master_id="user_1",
                room_id="room_1",
                title="Прокляття Страда",
                system="D&D 5e",
                starts_at=now + timedelta(hours=2),
                duration_minutes=180,
                max_players=5,
            ),
            Game(
                id="game_2",
                master_id="user_1",
                room_id="room_2",
                title="Поклик Ктулху: Маскарад",
                system="Call of Cthulhu",
                starts_at=now + timedelta(days=1, hours=1),
                duration_minutes=240,
                max_players=4,
            ),
        ]
        for game in games:
            if db.get(Game, game.id) is None:
                db.add(game)

        if (
            db.query(Enrollment.id).filter(Enrollment.game_id == "game_1", Enrollment.player_id == "user_2").first()
            is None
        ):
            db.add(
                Enrollment(
                    game_id="game_1",
                    player_id="user_2",
                    enrolled_at=now,
                )
            )

        db.commit()
        print("Базу даних успішно засіяно демо-даними.")
    finally:
        db.close()
