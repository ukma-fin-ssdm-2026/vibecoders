import itertools
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import store
from main import app
import db
from db import Base

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Жорстко підміняємо engine та SessionLocal у модулях
db.engine = engine
db.SessionLocal = TestingSessionLocal
store.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def isolated_store():
    # 1. Очищення кешу проксі та скидання стану пам'яті
    store.ROOMS._cache.clear()
    store.GAMES._cache.clear()
    store.USERS._cache.clear()
    store.TOKENS._cache.clear()
    store.LOGIN_FAILURES.clear()
    store.LOCKED_UNTIL.clear()
    store._game_sequence = itertools.count(3)

    # 2. На кожен тест створюємо нову чисту БД і заливаємо демо-дані
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    from models import User, Room, Token, Game, Enrollment

    try:
        rooms = [
            Room(id="room_1", name="Зала «Дракон»", capacity=8, is_blocked=False),
            Room(id="room_2", name="Зала «Лабіринт»", capacity=6, is_blocked=False),
            Room(id="room_3", name="Кімната «Таверна»", capacity=5, is_blocked=False),
        ]
        session.add_all(rooms)
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
        session.add_all(users)
        tokens = [
            Token(id="master-token", user_id="user_1"),
            Token(id="player-token", user_id="user_2"),
            Token(id="owner-token", user_id="user_3"),
        ]
        session.add_all(tokens)

        games = [
            Game(
                id="game_1",
                master_id="user_1",
                room_id="room_1",
                title="Прокляття Страда",
                system="D&D 5e",
                starts_at=datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc),
                duration_minutes=180,
                max_players=5,
            ),
            Game(
                id="game_2",
                master_id="user_1",
                room_id="room_2",
                title="Поклик Ктулху: Маскарад",
                system="Call of Cthulhu",
                starts_at=datetime(2026, 10, 11, 16, 0, tzinfo=timezone.utc),
                duration_minutes=240,
                max_players=4,
            ),
        ]
        session.add_all(games)

        enrollments = [
            Enrollment(
                game_id="game_1", player_id="user_2", enrolled_at=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
            )
        ]
        session.add_all(enrollments)

        session.commit()
    finally:
        session.close()

    yield

    # Видаляємо БД після тесту
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def master_headers():
    return {"Authorization": "Bearer master-token"}


@pytest.fixture
def player_headers():
    return {"Authorization": "Bearer player-token"}


@pytest.fixture
def owner_headers():
    return {"Authorization": "Bearer owner-token"}


@pytest.fixture
def game_payload():
    return {
        "title": "Нова кампанія",
        "system": "Pathfinder",
        "room_id": "room_3",
        "starts_at": "2026-11-01T10:00:00Z",
        "duration_minutes": 120,
        "max_players": 4,
    }


@pytest.fixture
def utc():
    def make(day, hour, minute=0):
        return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)

    return make
