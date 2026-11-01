import pytest

from notifications import list_user_notifications


@pytest.mark.requirement("FR-005")
def test_calendar_returns_all_rooms_bookings_and_blocks(client):
    response = client.get("/api/v1/rooms/calendar")
    assert response.status_code == 200
    rooms = response.json()["rooms"]
    assert [room["room_id"] for room in rooms] == ["room_1", "room_2", "room_3"]
    assert [booking["game_id"] for booking in rooms[0]["bookings"]] == ["game_1"]
    assert all(room["blocks"] == [] for room in rooms)


@pytest.mark.requirement("FR-005")
def test_calendar_filters_by_time_interval(client):
    response = client.get(
        "/api/v1/rooms/calendar",
        params={"starts_at": "2026-10-10T20:00:00Z", "ends_at": "2026-10-10T22:00:00Z"},
    )
    assert response.status_code == 200
    rooms = response.json()["rooms"]
    assert [booking["game_id"] for booking in rooms[0]["bookings"]] == ["game_1"]
    assert rooms[1]["bookings"] == []


@pytest.mark.requirement("FR-005")
def test_calendar_requires_both_bounds(client):
    response = client.get("/api/v1/rooms/calendar", params={"starts_at": "2026-10-10T20:00:00Z"})
    assert response.status_code == 400


@pytest.mark.requirement("US-003", "FR-007", "FR-011")
def test_room_block_cancels_overlapping_games_and_notifies_enrolled_players(client, owner_headers, game_payload):
    response = client.post(
        "/api/v1/rooms/room_1/blocks",
        json={"starts_at": "2026-10-10T19:00:00Z", "ends_at": "2026-10-10T22:00:00Z"},
        headers=owner_headers,
    )
    assert response.status_code == 201
    block = response.json()
    assert block["room_id"] == "room_1"
    assert block["starts_at"].startswith("2026-10-10T19:00:00")
    assert block["ends_at"].startswith("2026-10-10T22:00:00")

    assert client.get("/api/v1/games/game_1").status_code == 404
    [notification] = list_user_notifications("user_2")
    assert notification.game_id == "game_1"

    game_payload.update(room_id="room_1", starts_at="2026-10-10T20:00:00Z")
    conflict = client.post("/api/v1/games", json=game_payload, headers=owner_headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ROOM_BLOCKED"


@pytest.mark.requirement("US-003", "FR-007")
def test_room_block_requires_owner(client, master_headers):
    response = client.post(
        "/api/v1/rooms/room_3/blocks",
        json={"starts_at": "2026-11-01T10:00:00Z", "ends_at": "2026-11-01T12:00:00Z"},
        headers=master_headers,
    )
    assert response.status_code == 403


@pytest.mark.requirement("US-003", "FR-007")
def test_room_block_rejects_invalid_period(client, owner_headers):
    response = client.post(
        "/api/v1/rooms/room_3/blocks",
        json={"starts_at": "2026-11-01T12:00:00Z", "ends_at": "2026-11-01T10:00:00Z"},
        headers=owner_headers,
    )
    assert response.status_code == 400


@pytest.mark.requirement("US-003", "FR-007")
def test_room_block_can_be_removed_without_restoring_cancelled_games(client, owner_headers):
    created = client.post(
        "/api/v1/rooms/room_3/blocks",
        json={"starts_at": "2026-11-01T10:00:00Z", "ends_at": "2026-11-01T12:00:00Z"},
        headers=owner_headers,
    )
    assert created.status_code == 201
    block_id = created.json()["id"]

    deleted = client.delete(
        f"/api/v1/rooms/room_3/blocks/{block_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/rooms/room_3/bookings").json()["blocks"] == []


@pytest.mark.requirement("US-003", "FR-007")
def test_room_block_delete_returns_not_found(client, owner_headers):
    response = client.delete("/api/v1/rooms/room_3/blocks/99", headers=owner_headers)
    assert response.status_code == 404
