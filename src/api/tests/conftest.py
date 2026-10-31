import atexit
import itertools
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import db
import store
from db import Base
from main import app
from models import Enrollment, Game, Room, Token, User

# Створюємо тимчасову базу для тестів, щоб не залишати test.db у репозиторії
TEST_DB_DIR = tempfile.mkdtemp(prefix="vibecoders-tests-")
atexit.register(shutil.rmtree, TEST_DB_DIR, ignore_errors=True)
TEST_DATABASE_URL = f"sqlite:///{(Path(TEST_DB_DIR) / 'test.db').as_posix()}"

engine = db.configure_engine(
    create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Підміняємо engine та сесії для тестів
db.engine = engine
db.SessionLocal = TestingSessionLocal
store.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def isolated_store():
    # Спочатку видаляємо і створюємо таблиці, щоб проксі-об'єкти не падали
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Очищення кешу проксі та скидання стану пам'яті
    store.ROOMS._cache.clear()
    store.GAMES._cache.clear()
    store.USERS._cache.clear()
    store.TOKENS._cache.clear()
    store.LOGIN_FAILURES.clear()
    store.LOCKED_UNTIL.clear()
    store._game_sequence = itertools.count(3)

    session = TestingSessionLocal()
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
                starts_at=datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc).replace(tzinfo=None),
                duration_minutes=180,
                max_players=5,
            ),
            Game(
                id="game_2",
                master_id="user_1",
                room_id="room_2",
                title="Поклик Ктулху: Маскарад",
                system="Call of Cthulhu",
                starts_at=datetime(2026, 10, 11, 16, 0, tzinfo=timezone.utc).replace(tzinfo=None),
                duration_minutes=240,
                max_players=4,
            ),
        ]
        session.add_all(games)

        enrollments = [
            Enrollment(
                game_id="game_1",
                player_id="user_2",
                enrolled_at=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc).replace(tzinfo=None),
            )
        ]
        session.add_all(enrollments)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    yield


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
        "title": "Тестова гра",
        "system": "GURPS",
        "room_id": "room_3",
        "starts_at": "2026-10-10T14:00:00Z",
        "duration_minutes": 120,
        "max_players": 4,
    }


@pytest.fixture
def stub_now(monkeypatch):
    def fake_now(tz=None):
        return datetime(2026, 10, 2, tzinfo=timezone.utc)

    import routes.games
    import store

    monkeypatch.setattr(
        store,
        "datetime",
        type(
            "MockDateTime",
            (),
            {
                "now": fake_now,
                "fromisoformat": datetime.fromisoformat,
                "strptime": datetime.strptime,
            },
        ),
    )
    monkeypatch.setattr(
        routes.games,
        "datetime",
        type(
            "MockDateTime",
            (),
            {
                "now": fake_now,
                "fromisoformat": datetime.fromisoformat,
                "strptime": datetime.strptime,
            },
        ),
    )
    return fake_now


@pytest.fixture
def utc():
    def make(day, hour, minute=0):
        return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)

    return make
