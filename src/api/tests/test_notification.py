from datetime import datetime, timezone

import pytest

import notifications
from notifications import NOTIFICATIONS
from schemas import Player
from store import ENROLLMENTS


@pytest.fixture(autouse=True)
def clean_notifications():
    NOTIFICATIONS.clear()
    yield
    NOTIFICATIONS.clear()


def enroll(game_id, user_id, name):
    ENROLLMENTS[game_id].append(
        Player(user_id=user_id, name=name, enrolled_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    )


@pytest.mark.requirement("FR-011")
def test_deleting_game_notifies_enrolled_player(client, master_headers):
    response = client.delete("/api/v1/games/game_1", headers=master_headers)
    assert response.status_code == 204
    [notification] = NOTIFICATIONS["user_2"]
    assert notification.game_id == "game_1"
    assert "Прокляття Страда" in notification.message


@pytest.mark.requirement("FR-011")
def test_deleting_game_notifies_every_enrolled_player(client, master_headers):
    enroll("game_1", "user_3", "Олена")
    client.delete("/api/v1/games/game_1", headers=master_headers)
    assert sorted(NOTIFICATIONS) == ["user_2", "user_3"]


@pytest.mark.requirement("FR-011")
def test_deleting_game_without_players_sends_nothing(client, master_headers):
    response = client.delete("/api/v1/games/game_2", headers=master_headers)
    assert response.status_code == 204
    assert NOTIFICATIONS == {}


@pytest.mark.requirement("FR-011")
def test_forbidden_delete_does_not_notify_anyone(client, player_headers):
    response = client.delete("/api/v1/games/game_1", headers=player_headers)
    assert response.status_code == 403
    assert NOTIFICATIONS == {}


@pytest.mark.requirement("FR-011")
def test_notify_game_cancelled_returns_created_notifications():
    players = [Player(user_id="user_2", name="Марія", enrolled_at=datetime(2026, 10, 2, tzinfo=timezone.utc))]
    [created] = notifications.notify_game_cancelled("game_9", "Тест", players)
    assert NOTIFICATIONS["user_2"] == [created]
