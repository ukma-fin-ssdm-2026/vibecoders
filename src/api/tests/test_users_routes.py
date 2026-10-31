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


@pytest.mark.requirement("SEC-002")
def test_me_profile_is_available_to_authenticated_roles_only(client, player_headers, owner_headers):
    profile = client.get("/api/v1/users/me", headers=player_headers)
    assert profile.status_code == 200
    assert profile.json()["id"] == "user_2"
    assert profile.json()["email"] == "player@club.test"
    assert profile.json()["game_history"][0]["game_id"] == "game_1"

    owner_profile = client.get("/api/v1/users/me", headers=owner_headers)
    assert owner_profile.status_code == 200
    assert owner_profile.json()["id"] == "user_3"
    assert client.get("/api/v1/users/me").status_code == 401


@pytest.mark.requirement("SEC-002")
def test_me_profile_patch_updates_name_contacts_and_avatar(client, player_headers):
    response = client.patch(
        "/api/v1/users/me",
        json={"name": "  Марія К.  ", "contacts": "@maria", "avatar_url": "https://example.test/avatar.png"},
        headers=player_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Марія К."
    assert response.json()["contacts"] == "@maria"
    assert response.json()["avatar_url"] == "https://example.test/avatar.png"

    persisted = client.get("/api/v1/users/me", headers=player_headers).json()
    assert persisted["name"] == "Марія К."
    assert persisted["contacts"] == "@maria"
    assert persisted["avatar_url"] == "https://example.test/avatar.png"


@pytest.mark.requirement("SEC-002")
def test_me_profile_patch_can_clear_contacts_and_avatar(client, player_headers):
    response = client.patch(
        "/api/v1/users/me",
        json={"contacts": None, "avatar_url": None},
        headers=player_headers,
    )
    assert response.status_code == 200
    assert response.json()["contacts"] is None
    assert response.json()["avatar_url"] is None


@pytest.mark.parametrize(
    "payload",
    [{}, {"name": None}, {"name": "  "}, {"email": "new@example.test"}, {"contacts": "x" * 501}],
)
@pytest.mark.requirement("SEC-002")
def test_me_profile_patch_rejects_empty_invalid_or_unknown_fields(client, player_headers, payload):
    assert client.patch("/api/v1/users/me", json=payload, headers=player_headers).status_code == 400


@pytest.mark.requirement("SEC-002")
def test_me_profile_patch_rejects_anonymous_user(client):
    assert client.patch("/api/v1/users/me", json={"name": "New name"}).status_code == 401


@pytest.mark.requirement("SEC-002")
def test_owner_can_list_users_with_pagination_without_private_fields(client, owner_headers, player_headers):
    first_page = client.get("/api/v1/users", params={"limit": 2}, headers=owner_headers)
    assert first_page.status_code == 200
    assert [item["id"] for item in first_page.json()["items"]] == ["user_1", "user_2"]
    assert first_page.json()["pagination"] == {
        "limit": 2,
        "offset": 0,
        "total": 3,
        "has_more": True,
    }
    assert "email" not in first_page.json()["items"][0]

    second_page = client.get("/api/v1/users", params={"limit": 2, "offset": 2}, headers=owner_headers)
    assert [item["id"] for item in second_page.json()["items"]] == ["user_3"]
    assert second_page.json()["pagination"]["has_more"] is False
    assert client.get("/api/v1/users", headers=player_headers).status_code == 403
    assert client.get("/api/v1/users").status_code == 401


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
@pytest.mark.requirement("SEC-002")
def test_users_list_rejects_invalid_pagination(client, owner_headers, params):
    assert client.get("/api/v1/users", params=params, headers=owner_headers).status_code == 400


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
