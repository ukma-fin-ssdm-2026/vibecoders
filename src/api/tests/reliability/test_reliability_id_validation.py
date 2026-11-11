import logging

import pytest

import store
from store import hash_password, next_game_id


@pytest.mark.requirement("SEC-001")
def test_missing_password_salt_warns_and_uses_development_default(monkeypatch, caplog):
    monkeypatch.delenv("PASSWORD_SALT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    with caplog.at_level(logging.WARNING, logger="api.store"):
        salt = store._load_password_salt()

    assert salt == b"default-insecure-salt-for-dev"
    assert "using the insecure development salt" in caplog.text


@pytest.mark.requirement("SEC-001")
def test_missing_password_salt_fails_in_production(monkeypatch):
    monkeypatch.delenv("PASSWORD_SALT", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="PASSWORD_SALT must be configured in production"):
        store._load_password_salt()


@pytest.mark.requirement("SEC-001")
def test_configured_password_salt_is_used(monkeypatch):
    monkeypatch.setenv("PASSWORD_SALT", "configured-test-salt")
    monkeypatch.setenv("APP_ENV", "production")

    assert store._load_password_salt() == b"configured-test-salt"


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
