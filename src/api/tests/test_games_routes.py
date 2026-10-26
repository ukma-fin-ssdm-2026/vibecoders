from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import routes.games as games_module
from errors import ApiError
from schemas import GameBase, UserRole
from store import ENROLLMENTS, GAMES, ROOMS, GameRecord


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 5, 12, 0, tzinfo=tz)


def make_game_base(**overrides):
    data = {
        "title": "Тестова гра",
        "system": "D&D 5e",
        "room_id": "room_3",
        "starts_at": datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
        "duration_minutes": 120,
        "max_players": 4,
    }
    data.update(overrides)
    return GameBase(**data)


def test_list_games_returns_sorted_items_with_pagination(client):
    body = client.get("/api/v1/games").json()
    assert [g["id"] for g in body["items"]] == ["game_1", "game_2"]
    assert body["pagination"] == {"limit": 20, "offset": 0, "total": 2, "has_more": False}


def test_list_games_pagination_boundaries(client):
    first = client.get("/api/v1/games", params={"limit": 1}).json()
    assert [g["id"] for g in first["items"]] == ["game_1"]
    assert first["pagination"]["has_more"] is True
    last = client.get("/api/v1/games", params={"limit": 1, "offset": 1}).json()
    assert [g["id"] for g in last["items"]] == ["game_2"]
    assert last["pagination"]["has_more"] is False
    beyond = client.get("/api/v1/games", params={"offset": 2}).json()
    assert beyond["items"] == []
    assert beyond["pagination"]["total"] == 2


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"room_id": "x"}, {"master_id": "7"}])
def test_list_games_rejects_invalid_query(client, params):
    assert client.get("/api/v1/games", params=params).status_code == 400


def test_list_games_filters_by_room_and_master(client):
    by_room = client.get("/api/v1/games", params={"room_id": "room_2"}).json()
    assert [g["id"] for g in by_room["items"]] == ["game_2"]
    nobody = client.get("/api/v1/games", params={"master_id": "user_3"}).json()
    assert nobody["items"] == []


def test_get_game_returns_details_and_player_count(client):
    body = client.get("/api/v1/games/game_1").json()
    assert body["id"] == "game_1"
    assert body["current_players"] == 1


def test_get_game_unknown_id_returns_404(client):
    response = client.get("/api/v1/games/game_99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GAME_NOT_FOUND"


def test_get_game_malformed_id_returns_400(client):
    assert client.get("/api/v1/games/abc").status_code == 400


def test_create_game_success_sets_master_and_location(client, master_headers, game_payload):
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "game_3"
    assert body["master_id"] == "user_1"
    assert body["current_players"] == 0
    assert response.headers["location"] == "/api/v1/games/game_3"
    assert "game_3" in GAMES
    assert ENROLLMENTS["game_3"] == []


def test_create_game_forbidden_for_player(client, player_headers, game_payload):
    response = client.post("/api/v1/games", json=game_payload, headers=player_headers)
    assert response.status_code == 403
    assert len(GAMES) == 2


def test_create_game_unknown_room_returns_404(client, master_headers, game_payload):
    game_payload["room_id"] = "room_42"
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROOM_NOT_FOUND"


def test_create_game_in_blocked_room_returns_409(client, master_headers, game_payload):
    ROOMS["room_3"] = ROOMS["room_3"].model_copy(update={"is_blocked": True})
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROOM_BLOCKED"


def test_create_game_capacity_boundary(client, master_headers, game_payload):
    game_payload["max_players"] = 5
    assert client.post("/api/v1/games", json=game_payload, headers=master_headers).status_code == 201
    game_payload["max_players"] = 6
    game_payload["starts_at"] = "2026-11-02T10:00:00Z"
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROOM_CAPACITY_EXCEEDED"


def test_create_game_room_busy_returns_409(client, owner_headers, game_payload):
    game_payload.update(room_id="room_1", starts_at="2026-10-10T20:00:00Z")
    response = client.post("/api/v1/games", json=game_payload, headers=owner_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROOM_BUSY"


def test_create_game_starting_exactly_when_room_frees_up_is_allowed(client, owner_headers, game_payload):
    game_payload.update(room_id="room_1", starts_at="2026-10-10T21:00:00Z")
    response = client.post("/api/v1/games", json=game_payload, headers=owner_headers)
    assert response.status_code == 201


def test_create_game_master_busy_returns_409(client, master_headers, game_payload):
    game_payload.update(room_id="room_3", starts_at="2026-10-10T19:00:00Z")
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MASTER_BUSY"


def test_create_game_rejects_unknown_fields(client, master_headers, game_payload):
    game_payload["master_id"] = "user_3"
    assert client.post("/api/v1/games", json=game_payload, headers=master_headers).status_code == 400


def test_replace_game_by_master_updates_all_fields(client, master_headers, game_payload):
    response = client.put("/api/v1/games/game_1", json=game_payload, headers=master_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Нова кампанія"
    assert response.json()["master_id"] == "user_1"
    assert GAMES["game_1"].room_id == "room_3"


def test_replace_game_is_idempotent(client, master_headers, game_payload):
    first = client.put("/api/v1/games/game_1", json=game_payload, headers=master_headers)
    second = client.put("/api/v1/games/game_1", json=game_payload, headers=master_headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_replace_game_can_overlap_with_itself(client, master_headers, game_payload):
    game_payload.update(room_id="room_1", starts_at="2026-10-10T19:00:00Z")
    assert client.put("/api/v1/games/game_1", json=game_payload, headers=master_headers).status_code == 200


def test_replace_game_by_other_player_is_forbidden(client, player_headers, game_payload):
    assert client.put("/api/v1/games/game_1", json=game_payload, headers=player_headers).status_code == 403


def test_replace_game_below_enrolled_count_returns_409(client, master_headers, game_payload):
    game_payload["max_players"] = 2
    ENROLLMENTS["game_1"] = ENROLLMENTS["game_1"] * 3
    response = client.put("/api/v1/games/game_1", json=game_payload, headers=master_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MAX_PLAYERS_BELOW_ENROLLED"


def test_patch_game_changes_only_given_fields(client, master_headers):
    response = client.patch("/api/v1/games/game_1", json={"title": "Оновлена назва"}, headers=master_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Оновлена назва"
    assert body["system"] == "D&D 5e"
    assert body["max_players"] == 5


def test_patch_game_empty_body_returns_400(client, master_headers):
    response = client.patch("/api/v1/games/game_1", json={}, headers=master_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_game_owner_can_manage_foreign_game(client, owner_headers):
    response = client.patch("/api/v1/games/game_1", json={"duration_minutes": 60}, headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["master_id"] == "user_1"


def test_patch_game_to_conflicting_room_returns_409(client, master_headers):
    response = client.patch(
        "/api/v1/games/game_2", json={"room_id": "room_1", "starts_at": "2026-10-10T18:30:00Z"}, headers=master_headers
    )
    assert response.status_code == 409


def test_delete_game_removes_game_and_enrollments(client, master_headers):
    assert client.delete("/api/v1/games/game_1", headers=master_headers).status_code == 204
    assert "game_1" not in GAMES
    assert "game_1" not in ENROLLMENTS
    assert client.get("/api/v1/games/game_1").status_code == 404


def test_delete_game_forbidden_for_player_and_unauthenticated(client, player_headers):
    assert client.delete("/api/v1/games/game_1", headers=player_headers).status_code == 403
    assert client.delete("/api/v1/games/game_1").status_code == 401
    assert "game_1" in GAMES


def test_list_players_requires_authentication(client, player_headers):
    assert client.get("/api/v1/games/game_1/players").status_code == 401
    body = client.get("/api/v1/games/game_1/players", headers=player_headers).json()
    assert body["current_players"] == 1
    assert body["max_players"] == 5
    assert body["players"][0]["user_id"] == "user_2"


def test_enroll_player_uses_current_time_from_stubbed_clock(client, master_headers):
    with patch.object(games_module, "datetime", FrozenDatetime):
        response = client.post("/api/v1/games/game_2/players", headers=master_headers)
    assert response.status_code == 201
    assert response.json()["user_id"] == "user_1"
    assert response.json()["enrolled_at"].startswith("2026-10-05T12:00:00")
    assert response.headers["location"] == "/api/v1/games/game_2/players/user_1"


def test_enroll_player_twice_returns_409(client, player_headers):
    response = client.post("/api/v1/games/game_1/players", headers=player_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_ENROLLED"


def test_enroll_player_in_full_game_returns_409(client, owner_headers):
    GAMES["game_2"] = GAMES["game_2"].model_copy(update={"max_players": 2})
    client.post("/api/v1/games/game_2/players", headers={"Authorization": "Bearer master-token"})
    client.post("/api/v1/games/game_2/players", headers={"Authorization": "Bearer player-token"})
    response = client.post("/api/v1/games/game_2/players", headers=owner_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GAME_FULL"


def test_enroll_player_in_unknown_game_returns_404(client, player_headers):
    assert client.post("/api/v1/games/game_99/players", headers=player_headers).status_code == 404


@pytest.mark.parametrize("headers_fixture", ["player_headers", "master_headers", "owner_headers"])
def test_remove_player_allowed_for_self_master_and_owner(client, request, headers_fixture):
    headers = request.getfixturevalue(headers_fixture)
    response = client.delete("/api/v1/games/game_1/players/user_2", headers=headers)
    assert response.status_code == 204
    assert ENROLLMENTS["game_1"] == []


def test_remove_player_by_stranger_is_forbidden(client, master_headers):
    GAMES["game_2"] = GAMES["game_2"].model_copy(update={"master_id": "user_3"})
    response = client.delete("/api/v1/games/game_2/players/user_2", headers=master_headers)
    assert response.status_code == 403


def test_remove_player_not_enrolled_returns_404(client, master_headers):
    response = client.delete("/api/v1/games/game_2/players/user_2", headers=master_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ENROLLMENT_NOT_FOUND"


def test_enroll_last_free_seat_succeeds_then_game_is_full(client, master_headers, player_headers, owner_headers):
    GAMES["game_2"] = GAMES["game_2"].model_copy(update={"max_players": 2})
    assert client.post("/api/v1/games/game_2/players", headers=master_headers).status_code == 201
    assert client.post("/api/v1/games/game_2/players", headers=player_headers).status_code == 201
    assert client.get("/api/v1/games/game_2").json()["current_players"] == 2
    response = client.post("/api/v1/games/game_2/players", headers=owner_headers)
    assert response.status_code == 409
    assert len(ENROLLMENTS["game_2"]) == 2


def test_ensure_can_manage_allows_owner_and_own_master():
    record = GAMES["game_1"]
    games_module.ensure_can_manage(record, "user_3", UserRole.owner)
    games_module.ensure_can_manage(record, "user_1", UserRole.master)


def test_ensure_can_manage_rejects_foreign_master_and_player():
    record = GAMES["game_1"]
    with pytest.raises(ApiError) as error:
        games_module.ensure_can_manage(record, "user_9", UserRole.master)
    assert error.value.status_code == 403
    with pytest.raises(ApiError):
        games_module.ensure_can_manage(record, "user_2", UserRole.player)


def test_ensure_schedule_is_valid_accepts_free_slot():
    games_module.ensure_schedule_is_valid(make_game_base(), master_id="user_1")


def test_ensure_schedule_is_valid_reports_room_conflict_from_stubbed_lookup():
    busy = GameRecord(id="game_77", master_id="user_9", **make_game_base().model_dump())
    with patch.object(games_module, "find_busy_game", return_value=busy) as lookup:
        with pytest.raises(ApiError) as error:
            games_module.ensure_schedule_is_valid(make_game_base(), master_id="user_1")
    assert error.value.code == "ROOM_BUSY"
    assert "game_77" in error.value.message
    assert lookup.call_args.kwargs["room_id"] == "room_3"


def test_ensure_schedule_is_valid_checks_master_when_room_is_free():
    busy = GameRecord(id="game_88", master_id="user_1", **make_game_base().model_dump())
    with patch.object(games_module, "find_busy_game", side_effect=[None, busy]) as lookup:
        with pytest.raises(ApiError) as error:
            games_module.ensure_schedule_is_valid(make_game_base(), master_id="user_1")
    assert error.value.code == "MASTER_BUSY"
    assert lookup.call_count == 2
