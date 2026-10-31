import pytest


@pytest.mark.requirement("SEC-002")
def test_personal_profile_is_private_to_user_and_owner(client, player_headers, owner_headers):
    own_profile = client.get("/api/v1/users/user_2", headers=player_headers)
    assert own_profile.status_code == 200
    assert own_profile.json()["email"] == "player@club.test"
    assert own_profile.json()["game_history"][0]["game_id"] == "game_1"

    other_profile = client.get("/api/v1/users/user_1", headers=player_headers)
    assert other_profile.status_code == 403

    owner_profile = client.get("/api/v1/users/user_2", headers=owner_headers)
    assert owner_profile.status_code == 200
    assert owner_profile.json()["email"] == "player@club.test"


@pytest.mark.requirement("US-004", "FR-008", "SEC-002")
def test_owner_can_block_user_and_blocked_user_cannot_login_or_use_token(client, owner_headers, player_headers):
    response = client.patch(
        "/api/v1/users/user_2",
        json={"is_blocked": True},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": "user_2",
        "name": "Марія",
        "role": "player",
        "is_blocked": True,
    }

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "player@club.test", "password": "player-pass-1"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/games/game_1/players", headers=player_headers).status_code == 401
    owner_profile = client.get("/api/v1/users/user_2", headers=owner_headers)
    assert owner_profile.status_code == 200
    assert owner_profile.json()["is_blocked"] is True


@pytest.mark.requirement("SEC-004")
def test_blocked_email_cannot_be_registered_again_within_300ms(client, owner_headers):
    from time import perf_counter

    assert (
        client.patch(
            "/api/v1/users/user_2",
            json={"is_blocked": True},
            headers=owner_headers,
        ).status_code
        == 200
    )
    started = perf_counter()
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Інший гравець", "email": "player@club.test", "password": "new-player-pass-1"},
    )
    elapsed = perf_counter() - started

    assert response.status_code == 409
    assert elapsed <= 0.3


@pytest.mark.requirement("US-004", "FR-008", "SEC-002")
def test_only_owner_can_block_users_and_owner_cannot_block_self(client, player_headers, owner_headers):
    forbidden = client.patch(
        "/api/v1/users/user_1",
        json={"is_blocked": True},
        headers=player_headers,
    )
    assert forbidden.status_code == 403

    self_block = client.patch(
        "/api/v1/users/user_3",
        json={"is_blocked": True},
        headers=owner_headers,
    )
    assert self_block.status_code == 409
    assert self_block.json()["error"]["code"] == "CANNOT_BLOCK_SELF"
