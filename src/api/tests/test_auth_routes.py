from unittest.mock import patch

import pytest


@pytest.mark.parametrize(
    "email, password, token, role",
    [
        ("master@club.test", "master-pass-1", "master-token", "master"),
        ("player@club.test", "player-pass-1", "player-token", "player"),
        ("owner@club.test", "owner-pass-1", "owner-token", "owner"),
    ],
)
def test_login_returns_token_and_role(client, email, password, token, role):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json() == {"access_token": token, "token_type": "bearer", "role": role}


def test_login_wrong_password_and_unknown_email_look_identical(client):
    wrong_password = client.post("/api/v1/auth/login", json={"email": "master@club.test", "password": "wrong-pass-1"})
    unknown_email = client.post("/api/v1/auth/login", json={"email": "ghost@club.test", "password": "master-pass-1"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.headers["www-authenticate"] == "Bearer"


def test_login_password_of_another_user_is_rejected(client):
    response = client.post("/api/v1/auth/login", json={"email": "master@club.test", "password": "owner-pass-1"})
    assert response.status_code == 401


def test_login_rejects_short_password_with_validation_error(client):
    response = client.post("/api/v1/auth/login", json={"email": "master@club.test", "password": "short"})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "body.password"


def test_login_rejects_extra_fields(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "master@club.test", "password": "master-pass-1", "remember": True},
    )
    assert response.status_code == 400


def test_login_does_not_check_password_for_unknown_email(client):
    with patch("routes.auth.verify_password") as verify:
        response = client.post("/api/v1/auth/login", json={"email": "ghost@club.test", "password": "whatever-1"})
    assert response.status_code == 401
    verify.assert_not_called()


def test_login_delegates_password_check_to_verify_password(client):
    with patch("routes.auth.verify_password", return_value=True) as verify:
        response = client.post("/api/v1/auth/login", json={"email": "player@club.test", "password": "stub-pass-1"})
    assert response.status_code == 200
    assert response.json()["access_token"] == "player-token"
    assert verify.call_args.args[0] == "stub-pass-1"


def test_issued_token_grants_access_to_protected_endpoint(client):
    login = client.post("/api/v1/auth/login", json={"email": "player@club.test", "password": "player-pass-1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/games/game_1/players", headers=headers)
    assert response.status_code == 200
