import pytest

import store
from store import hash_password, next_game_id


@pytest.mark.technical
@pytest.mark.parametrize("existing_id", ["user_²", "user_٩", "user_abc", "user_", "user_1a"])
@pytest.mark.requirement("US-009", "SEC-004")
def test_registration_ignores_malformed_id_suffixes(existing_id):
    db = store.SessionLocal()
    try:
        db.add(
            store.UserModel(
                id=existing_id,
                email="legacy.invalid@club.test",
                password_hash=hash_password("legacy-password"),
                name="Legacy user",
                role="player",
            )
        )
        db.commit()
    finally:
        db.close()

    created = store.create_registered_user("New player", "new.player@club.test", "new-password")

    assert created is not None
    assert created[0] == "user_4"


@pytest.mark.technical
@pytest.mark.parametrize("game_id", ["game_²", "game_٩", "game_abc"])
@pytest.mark.requirement("US-002")
def test_next_game_id_ignores_malformed_id_suffixes(game_id):
    db = store.SessionLocal()
    try:
        reference = db.get(store.GameModel, "game_1")
        db.add(
            store.GameModel(
                id=game_id,
                master_id=reference.master_id,
                room_id=reference.room_id,
                title=reference.title,
                system=reference.system,
                starts_at=reference.starts_at,
                duration_minutes=reference.duration_minutes,
                max_players=reference.max_players,
            )
        )
        db.commit()
    finally:
        db.close()

    assert next_game_id() == "game_3"
