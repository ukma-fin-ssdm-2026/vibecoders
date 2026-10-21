import pytest

from store import GAMES, ROOMS


def test_list_rooms_sorted_by_id_with_pagination(client):
    body = client.get("/api/v1/rooms").json()
    assert [r["id"] for r in body["items"]] == ["room_1", "room_2", "room_3"]
    assert body["pagination"] == {"limit": 20, "offset": 0, "total": 3, "has_more": False}


def test_list_rooms_page_boundaries(client):
    page = client.get("/api/v1/rooms", params={"limit": 2, "offset": 1}).json()
    assert [r["id"] for r in page["items"]] == ["room_2", "room_3"]
    assert page["pagination"]["has_more"] is False
    first = client.get("/api/v1/rooms", params={"limit": 2}).json()
    assert first["pagination"]["has_more"] is True


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_rooms_rejects_invalid_pagination(client, params):
    assert client.get("/api/v1/rooms", params=params).status_code == 400


def test_get_room_returns_capacity_and_status(client):
    assert client.get("/api/v1/rooms/room_2").json() == {
        "id": "room_2",
        "name": "Зала «Лабіринт»",
        "capacity": 6,
        "is_blocked": False,
        "current_players": 0,
    }


def test_get_room_unknown_returns_404(client):
    response = client.get("/api/v1/rooms/room_99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROOM_NOT_FOUND"


def test_get_room_malformed_id_returns_400(client):
    assert client.get("/api/v1/rooms/hall_1").status_code == 400


def test_room_bookings_lists_game_slots_with_end_time(client):
    body = client.get("/api/v1/rooms/room_1/bookings").json()
    assert body["room_id"] == "room_1"
    assert body["is_blocked"] is False
    assert len(body["bookings"]) == 1
    booking = body["bookings"][0]
    assert booking["game_id"] == "game_1"
    assert booking["starts_at"].startswith("2026-10-10T18:00:00")
    assert booking["ends_at"].startswith("2026-10-10T21:00:00")


def test_room_bookings_empty_for_free_room(client):
    assert client.get("/api/v1/rooms/room_3/bookings").json()["bookings"] == []


def test_room_bookings_are_sorted_by_start_time(client, owner_headers, game_payload):
    game_payload.update(room_id="room_1", starts_at="2026-10-09T10:00:00Z")
    assert client.post("/api/v1/games", json=game_payload, headers=owner_headers).status_code == 201
    bookings = client.get("/api/v1/rooms/room_1/bookings").json()["bookings"]
    assert [b["game_id"] for b in bookings] == ["game_3", "game_1"]


def test_room_bookings_unknown_room_returns_404(client):
    assert client.get("/api/v1/rooms/room_99/bookings").status_code == 404


def test_block_room_requires_owner(client, master_headers, player_headers):
    assert client.patch("/api/v1/rooms/room_3", json={"is_blocked": True}, headers=master_headers).status_code == 403
    assert client.patch("/api/v1/rooms/room_3", json={"is_blocked": True}, headers=player_headers).status_code == 403
    assert client.patch("/api/v1/rooms/room_3", json={"is_blocked": True}).status_code == 401
    assert ROOMS["room_3"].is_blocked is False


def test_block_room_without_games_succeeds(client, owner_headers):
    response = client.patch("/api/v1/rooms/room_3", json={"is_blocked": True}, headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["is_blocked"] is True
    assert ROOMS["room_3"].is_blocked is True


def test_block_room_with_games_returns_409(client, owner_headers):
    response = client.patch("/api/v1/rooms/room_1", json={"is_blocked": True}, headers=owner_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROOM_HAS_GAMES"
    assert ROOMS["room_1"].is_blocked is False


def test_unblock_room_with_games_is_allowed(client, owner_headers):
    ROOMS["room_1"] = ROOMS["room_1"].model_copy(update={"is_blocked": True})
    response = client.patch("/api/v1/rooms/room_1", json={"is_blocked": False}, headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["is_blocked"] is False


def test_block_room_becomes_free_after_games_are_deleted(client, owner_headers):
    del GAMES["game_1"]
    response = client.patch("/api/v1/rooms/room_1", json={"is_blocked": True}, headers=owner_headers)
    assert response.status_code == 200


def test_block_room_requires_is_blocked_field(client, owner_headers):
    assert client.patch("/api/v1/rooms/room_3", json={}, headers=owner_headers).status_code == 400
