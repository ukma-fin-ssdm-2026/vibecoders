import pytest

from store import GAMES, ROOMS

GAMES_URL = "/api/v1/games"

RULES = [
    pytest.param("player", "room_3", False, "2026-11-01T10:00:00Z", 4, 403, "FORBIDDEN", id="DT-1"),
    pytest.param("master", "room_9", False, "2026-11-01T10:00:00Z", 4, 404, "ROOM_NOT_FOUND", id="DT-2"),
    pytest.param("master", "room_3", True, "2026-11-01T10:00:00Z", 4, 409, "ROOM_BLOCKED", id="DT-3"),
    pytest.param("master", "room_3", False, "2026-11-01T10:00:00Z", 6, 409, "ROOM_CAPACITY_EXCEEDED", id="DT-4"),
    pytest.param("owner", "room_1", False, "2026-10-10T18:00:00Z", 4, 409, "ROOM_BUSY", id="DT-5"),
    pytest.param("master", "room_3", False, "2026-10-10T18:00:00Z", 4, 409, "MASTER_BUSY", id="DT-6"),
    pytest.param("master", "room_3", False, "2026-11-01T10:00:00Z", 4, 201, None, id="DT-7"),
    pytest.param("master", "room_1", False, "2026-10-10T18:00:00Z", 4, 409, "ROOM_BUSY", id="DT-8"),
    pytest.param("master", "room_3", True, "2026-10-10T18:00:00Z", 6, 409, "ROOM_BLOCKED", id="DT-9"),
]


@pytest.mark.requirement("US-002", "REL-002")
@pytest.mark.parametrize("role, room_id, blocked, starts_at, max_players, status, code", RULES)
def test_create_game_decision_table(
    client, game_payload, request, role, room_id, blocked, starts_at, max_players, status, code
):
    headers = request.getfixturevalue(f"{role}_headers")
    ROOMS["room_3"] = ROOMS["room_3"].model_copy(update={"is_blocked": blocked})
    games_before = set(GAMES)
    game_payload.update(room_id=room_id, starts_at=starts_at, max_players=max_players)

    response = client.post(GAMES_URL, json=game_payload, headers=headers)

    assert response.status_code == status
    if code is None:
        assert set(GAMES) - games_before == {response.json()["id"]}
    else:
        assert response.json()["error"]["code"] == code
        assert set(GAMES) == games_before
