import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from main import app
from notifications import list_user_notifications
from store import delete_game_with_notifications

BLOCK_OVER_GAME_1 = {"starts_at": "2026-10-10T19:00:00Z", "ends_at": "2026-10-10T22:00:00Z"}


def notification_write_fails(*args, **kwargs):
    raise OperationalError("INSERT INTO notifications", {}, Exception("disk I/O error"))


@pytest.fixture
def tolerant_client():
    return TestClient(app, raise_server_exceptions=False)


def players_of_game_1(client, headers):
    response = client.get("/api/v1/games/game_1/players", headers=headers)
    assert response.status_code == 200
    return [player["user_id"] for player in response.json()["players"]]


@pytest.mark.technical
def test_room_block_is_rolled_back_when_notification_write_fails(tolerant_client, monkeypatch, owner_headers):
    monkeypatch.setattr("routes.rooms.build_cancellation_rows", notification_write_fails)

    response = tolerant_client.post("/api/v1/rooms/room_1/blocks", json=BLOCK_OVER_GAME_1, headers=owner_headers)

    assert response.status_code == 503
    assert tolerant_client.get("/api/v1/games/game_1").status_code == 200
    assert tolerant_client.get("/api/v1/rooms/room_1/bookings").json()["blocks"] == []
    assert players_of_game_1(tolerant_client, owner_headers) == ["user_2"]
    assert list_user_notifications() == []


@pytest.mark.technical
def test_room_block_succeeds_again_after_the_fault_is_gone(tolerant_client, monkeypatch, owner_headers):
    monkeypatch.setattr("routes.rooms.build_cancellation_rows", notification_write_fails)
    assert (
        tolerant_client.post("/api/v1/rooms/room_1/blocks", json=BLOCK_OVER_GAME_1, headers=owner_headers).status_code
        == 503
    )

    monkeypatch.undo()

    response = tolerant_client.post("/api/v1/rooms/room_1/blocks", json=BLOCK_OVER_GAME_1, headers=owner_headers)
    assert response.status_code == 201
    assert tolerant_client.get("/api/v1/games/game_1").status_code == 404
    [notification] = list_user_notifications("user_2")
    assert notification.game_id == "game_1"


@pytest.mark.technical
def test_delete_game_keeps_game_and_players_when_notification_write_fails(tolerant_client, monkeypatch, master_headers):
    monkeypatch.setattr("store.build_cancellation_rows", notification_write_fails)

    response = tolerant_client.delete("/api/v1/games/game_1", headers=master_headers)

    assert response.status_code == 503
    assert tolerant_client.get("/api/v1/games/game_1").status_code == 200
    assert players_of_game_1(tolerant_client, master_headers) == ["user_2"]
    assert list_user_notifications() == []


@pytest.mark.technical
def test_delete_game_notifies_every_enrolled_player_in_one_step(
    tolerant_client, master_headers, player_headers, owner_headers
):
    assert tolerant_client.post("/api/v1/games/game_1/players", headers=owner_headers).status_code == 201

    response = tolerant_client.delete("/api/v1/games/game_1", headers=master_headers)

    assert response.status_code == 204
    assert tolerant_client.get("/api/v1/games/game_1").status_code == 404
    assert sorted(n.user_id for n in list_user_notifications()) == ["user_2", "user_3"]


@pytest.mark.technical
def test_delete_game_with_notifications_ignores_missing_game():
    delete_game_with_notifications("game_404")

    assert list_user_notifications() == []
