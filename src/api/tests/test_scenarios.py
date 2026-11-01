import pytest

GAMES_URL = "/api/v1/games"
ROOM_1 = "/api/v1/rooms/room_1"
ROOM_3 = "/api/v1/rooms/room_3"


@pytest.mark.requirement("US-002")
def test_scenario_master_books_free_room_and_slot_appears_in_calendar(client, master_headers, game_payload):
    created = client.post(GAMES_URL, json=game_payload, headers=master_headers)
    assert created.status_code == 201

    bookings = client.get(f"{ROOM_3}/bookings").json()["bookings"]

    assert [b["game_id"] for b in bookings] == [created.json()["id"]]
    assert bookings[0]["starts_at"].startswith(game_payload["starts_at"].split("Z")[0])


@pytest.mark.requirement("US-008", "US-002")
def test_scenario_deleting_game_frees_its_slot_for_a_new_booking(client, master_headers, game_payload):
    game_payload.update(room_id="room_1", starts_at="2026-10-10T18:00:00Z", duration_minutes=180)
    assert client.post(GAMES_URL, json=game_payload, headers=master_headers).status_code == 409

    assert client.delete(f"{GAMES_URL}/game_1", headers=master_headers).status_code == 204

    assert client.get(f"{ROOM_1}/bookings").json()["bookings"] == []
    assert client.post(GAMES_URL, json=game_payload, headers=master_headers).status_code == 201


@pytest.mark.requirement("US-003", "US-002")
def test_scenario_blocked_room_rejects_new_games(client, owner_headers, master_headers, game_payload):
    assert client.patch(ROOM_3, json={"is_blocked": True}, headers=owner_headers).status_code == 200

    response = client.post(GAMES_URL, json=game_payload, headers=master_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROOM_BLOCKED"
