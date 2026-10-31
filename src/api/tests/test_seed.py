import asyncio

import pytest

import db
import main
import seed
from models import Enrollment, Game, Room, RoomBlock, Token, User


@pytest.mark.technical
def test_seed_restores_missing_entities_without_overwriting_existing_data(monkeypatch):
    monkeypatch.setattr(seed, "SessionLocal", db.SessionLocal)

    session = db.SessionLocal()
    try:
        for model in (Enrollment, Game, RoomBlock, Token, User, Room):
            session.query(model).delete()
        session.commit()
    finally:
        session.close()

    seed.seed_db()
    session = db.SessionLocal()
    try:
        session.get(User, "user_1").name = "Ім'я, встановлене адміністратором"
        session.query(Room).filter(Room.id == "room_3").delete()
        session.query(Game).filter(Game.id == "game_2").delete()
        session.query(Token).filter(Token.id == "owner-token").delete()
        session.query(User).filter(User.id == "user_3").delete()
        session.commit()
    finally:
        session.close()

    seed.seed_db()
    seed.seed_db()

    session = db.SessionLocal()
    try:
        assert session.query(Room).count() == 3
        assert session.query(User).count() == 3
        assert session.query(Token).count() == 3
        assert session.query(Game).count() == 2
        assert session.query(Enrollment).count() == 1
        assert session.get(User, "user_1").name == "Ім'я, встановлене адміністратором"
        assert session.get(Room, "room_3") is not None
        assert session.get(Game, "game_2") is not None
        assert session.get(Token, "owner-token").user_id == "user_3"
    finally:
        session.close()


@pytest.mark.technical
def test_application_lifespan_runs_database_seed(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "seed_db", lambda: calls.append("seeded"))
    monkeypatch.setattr(main, "save_openapi_spec", lambda app: None)

    async def run_lifespan():
        async with main.app.router.lifespan_context(main.app):
            pass

    asyncio.run(run_lifespan())

    assert calls == ["seeded"]
