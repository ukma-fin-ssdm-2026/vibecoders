from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import routes.auth as auth_module
import store


@pytest.mark.parametrize(
    "email, password, token, role",
    [
        ("master@club.test", "master-pass-1", "master-token", "master"),
        ("player@club.test", "player-pass-1", "player-token", "player"),
        ("owner@club.test", "owner-pass-1", "owner-token", "owner"),
    ],
)
@pytest.mark.technical
def test_login_returns_token_and_role(client, email, password, token, role):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json() == {"access_token": token, "token_type": "bearer", "role": role}


@pytest.mark.technical
def test_login_wrong_password_and_unknown_email_look_identical(client):
    wrong_password = client.post("/api/v1/auth/login", json={"email": "master@club.test", "password": "wrong-pass-1"})
    unknown_email = client.post("/api/v1/auth/login", json={"email": "ghost@club.test", "password": "master-pass-1"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.headers["www-authenticate"] == "Bearer"


@pytest.mark.technical
def test_login_password_of_another_user_is_rejected(client):
    response = client.post("/api/v1/auth/login", json={"email": "master@club.test", "password": "owner-pass-1"})
    assert response.status_code == 401


@pytest.mark.requirement("US-009", "FR-001", "SEC-001", "SEC-004")
def test_register_creates_player_with_hashed_password_and_token(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Новий гравець", "email": "New.Player@club.test", "password": "new-player-pass-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "player"
    assert body["access_token"]
    from db import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "new.player@club.test").one()
        assert user.password_hash != "new-player-pass-1"
        assert (
            client.get(
                "/api/v1/games/game_1/players",
                headers={"Authorization": f"Bearer {body['access_token']}"},
            ).status_code
            == 200
        )
    finally:
        db.close()


@pytest.mark.requirement("SEC-004")
def test_register_rejects_existing_account_email(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Інший гравець", "email": "PLAYER@club.test", "password": "new-player-pass-1"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.technical
def test_login_rejects_short_password_with_validation_error(client):
    response = client.post("/api/v1/auth/login", json={"email": "master@club.test", "password": "short"})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "body.password"


@pytest.mark.technical
def test_login_rejects_extra_fields(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "master@club.test", "password": "master-pass-1", "remember": True},
    )
    assert response.status_code == 400


@pytest.mark.technical
def test_login_does_not_check_password_for_unknown_email(client):
    with patch("routes.auth.verify_password") as verify:
        response = client.post("/api/v1/auth/login", json={"email": "ghost@club.test", "password": "whatever-1"})
    assert response.status_code == 401
    verify.assert_not_called()


@pytest.mark.requirement("SEC-001")
def test_login_delegates_password_check_to_verify_password(client):
    with patch("routes.auth.verify_password", return_value=True) as verify:
        response = client.post("/api/v1/auth/login", json={"email": "player@club.test", "password": "stub-pass-1"})
    assert response.status_code == 200
    assert response.json()["access_token"] == "player-token"
    assert verify.call_args.args[0] == "stub-pass-1"


@pytest.mark.technical
def test_issued_token_grants_access_to_protected_endpoint(client):
    login = client.post("/api/v1/auth/login", json={"email": "player@club.test", "password": "player-pass-1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/games/game_1/players", headers=headers)
    assert response.status_code == 200


# SEC-003: після 5 невдалих спроб входу за 15 хвилин акаунт блокується на 15 хвилин.
# Специфікація поведінки: HTTP 429, код ACCOUNT_LOCKED, заголовок Retry-After (секунди до розблокування).
# Стан лічильників тримають store.LOGIN_FAILURES (email -> час невдалих спроб)
# і store.LOCKED_UNTIL (email -> час розблокування).

LOGIN_URL = "/api/v1/auth/login"
MASTER_EMAIL = "master@club.test"
LOCK_MINUTES = 15


@pytest.fixture(autouse=True)
def clean_login_state():
    def clear():
        for name in ("LOGIN_FAILURES", "LOCKED_UNTIL"):
            getattr(store, name, {}).clear()

    clear()
    yield
    clear()


@pytest.fixture
def clock():
    class Clock(datetime):
        current = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    with patch.object(auth_module, "datetime", Clock, create=True):
        yield Clock


def login(client, email=MASTER_EMAIL, password="master-pass-1"):
    return client.post(LOGIN_URL, json={"email": email, "password": password})


def fail_login(client, times, email=MASTER_EMAIL):
    for _ in range(times):
        assert login(client, email, "wrong-pass-1").status_code == 401


@pytest.mark.requirement("SEC-003")
def test_fifth_failed_login_returns_401_and_sixth_attempt_is_locked(client, clock):
    fail_login(client, 5)
    response = login(client, password="wrong-pass-1")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ACCOUNT_LOCKED"


@pytest.mark.requirement("SEC-003")
def test_locked_account_rejects_correct_password_and_reports_retry_after(client, clock):
    fail_login(client, 5)
    assert login(client).status_code == 429
    assert login(client).headers["retry-after"] == str(LOCK_MINUTES * 60)
    clock.current += timedelta(minutes=5)
    assert login(client).headers["retry-after"] == str((LOCK_MINUTES - 5) * 60)


@pytest.mark.requirement("SEC-003")
def test_four_failed_logins_do_not_lock_and_success_resets_counter(client, clock):
    fail_login(client, 4)
    assert login(client).status_code == 200
    fail_login(client, 4)
    assert login(client).status_code == 200


@pytest.mark.requirement("SEC-003")
def test_lock_expires_exactly_after_15_minutes(client, clock):
    fail_login(client, 5)
    clock.current += timedelta(minutes=14, seconds=59)
    assert login(client).status_code == 429
    clock.current += timedelta(seconds=1)
    assert login(client).status_code == 200


@pytest.mark.requirement("SEC-003")
def test_attempts_during_lock_do_not_extend_it(client, clock):
    fail_login(client, 5)
    clock.current += timedelta(minutes=10)
    assert login(client).status_code == 429
    clock.current += timedelta(minutes=5)
    assert login(client).status_code == 200


@pytest.mark.requirement("SEC-003")
def test_failures_older_than_15_minutes_are_not_counted(client, clock):
    fail_login(client, 3)
    clock.current += timedelta(minutes=16)
    fail_login(client, 2)
    assert login(client).status_code == 200


@pytest.mark.requirement("SEC-003")
def test_lock_applies_only_to_the_attacked_account(client, clock):
    fail_login(client, 5)
    assert login(client).status_code == 429
    assert login(client, "player@club.test", "player-pass-1").status_code == 200


@pytest.mark.requirement("SEC-003")
def test_unknown_email_gets_locked_the_same_way_as_known_one(client, clock):
    fail_login(client, 5, email="ghost@club.test")
    fail_login(client, 5)
    unknown = login(client, "ghost@club.test", "wrong-pass-1")
    known = login(client, MASTER_EMAIL, "wrong-pass-1")
    assert unknown.status_code == known.status_code == 429
    assert unknown.json() == known.json()
