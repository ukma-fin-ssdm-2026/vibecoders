from datetime import datetime, timezone

import pytest

import notifications
from notifications import list_user_notifications, mark_notification_read
from schemas import Player
from store import ENROLLMENTS


def enroll(game_id, user_id, name):
    ENROLLMENTS[game_id].append(
        Player(user_id=user_id, name=name, enrolled_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    )


def player(user_id="user_2", name="Марія"):
    return Player(user_id=user_id, name=name, enrolled_at=datetime(2026, 10, 2, tzinfo=timezone.utc))


@pytest.mark.requirement("FR-011")
def test_deleting_game_notifies_enrolled_player(client, master_headers):
    response = client.delete("/api/v1/games/game_1", headers=master_headers)
    assert response.status_code == 204
    [notification] = list_user_notifications("user_2")
    assert notification.game_id == "game_1"
    assert "Прокляття Страда" in notification.message


@pytest.mark.requirement("FR-011")
def test_deleting_game_notifies_every_enrolled_player(client, master_headers):
    enroll("game_1", "user_3", "Олена")
    client.delete("/api/v1/games/game_1", headers=master_headers)
    assert sorted({n.user_id for n in list_user_notifications()}) == ["user_2", "user_3"]


@pytest.mark.requirement("FR-011")
def test_deleting_game_without_players_sends_nothing(client, master_headers):
    response = client.delete("/api/v1/games/game_2", headers=master_headers)
    assert response.status_code == 204
    assert list_user_notifications() == []


@pytest.mark.requirement("FR-011")
def test_forbidden_delete_does_not_notify_anyone(client, player_headers):
    response = client.delete("/api/v1/games/game_1", headers=player_headers)
    assert response.status_code == 403
    assert list_user_notifications() == []


@pytest.mark.requirement("FR-011")
def test_notify_game_cancelled_returns_created_notifications():
    [created] = notifications.notify_game_cancelled("game_9", "Тест", [player()])
    assert created.id is not None
    assert created.is_read is False
    assert list_user_notifications("user_2") == [created]


@pytest.mark.requirement("FR-011")
def test_notify_game_cancelled_without_players_creates_nothing():
    assert notifications.notify_game_cancelled("game_9", "Тест", []) == []
    assert list_user_notifications() == []


@pytest.mark.requirement("FR-011")
def test_notifications_are_stored_in_database_and_survive_game_deletion(client, master_headers):
    client.delete("/api/v1/games/game_1", headers=master_headers)
    assert client.get("/api/v1/games/game_1").status_code == 404
    [notification] = list_user_notifications("user_2")
    assert notification.game_id == "game_1"
    assert notification.created_at.tzinfo is not None


@pytest.mark.requirement("FR-011")
def test_list_notifications_is_newest_first_and_supports_paging():
    notifications.notify_game_cancelled("game_7", "Перша", [player()])
    notifications.notify_game_cancelled("game_8", "Друга", [player()])
    notifications.notify_game_cancelled("game_9", "Третя", [player()])
    assert [n.game_id for n in list_user_notifications("user_2")] == ["game_9", "game_8", "game_7"]
    assert [n.game_id for n in list_user_notifications("user_2", limit=2)] == ["game_9", "game_8"]
    assert [n.game_id for n in list_user_notifications("user_2", limit=2, offset=2)] == ["game_7"]
    assert list_user_notifications("user_3") == []


@pytest.mark.requirement("FR-011")
def test_mark_notification_read_filters_unread_and_checks_owner():
    [first, second] = notifications.notify_game_cancelled("game_9", "Тест", [player(), player("user_3", "Олена")])
    marked = mark_notification_read("user_2", first.id)
    assert marked is not None and marked.is_read is True
    assert list_user_notifications("user_2", unread_only=True) == []
    assert [n.id for n in list_user_notifications("user_3", unread_only=True)] == [second.id]
    # чуже або неіснуюче сповіщення не змінюється
    assert mark_notification_read("user_2", second.id) is None
    assert mark_notification_read("user_2", 9999) is None
    assert list_user_notifications("user_3")[0].is_read is False


@pytest.mark.requirement("FR-011")
def test_notifications_endpoint_returns_only_current_users_notifications(client, player_headers, owner_headers):
    player = Player(user_id="user_2", name="Марія", enrolled_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    owner = Player(user_id="user_3", name="Олена", enrolled_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    notifications.notify_game_cancelled("game_1", "Перша гра", [player])
    notifications.notify_game_cancelled("game_2", "Друга гра", [player])
    notifications.notify_game_cancelled("game_3", "Приватне сповіщення власника", [owner])

    response = client.get("/api/v1/notifications", headers=player_headers)

    assert response.status_code == 200
    assert [item["game_id"] for item in response.json()] == ["game_2", "game_1"]
    assert all("Приватне сповіщення власника" not in item["message"] for item in response.json())
    assert response.json()[0]["is_read"] is False
    assert client.get("/api/v1/notifications", headers=owner_headers).json()[0]["game_id"] == "game_3"


@pytest.mark.requirement("FR-011")
def test_notifications_endpoint_returns_empty_list_and_requires_authentication(client, player_headers):
    assert client.get("/api/v1/notifications", headers=player_headers).json() == []
    assert client.get("/api/v1/notifications").status_code == 401
