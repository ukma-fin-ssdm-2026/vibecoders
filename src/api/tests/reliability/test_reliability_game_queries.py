"""R-14: фільтр, сортування й пагінація ігор виконуються в БД, а не повним скануванням у Python."""

from datetime import datetime, timedelta

import pytest

import store
from models import Game


def add_games(count, room_id="room_3", master_id="user_2"):
    db = store.SessionLocal()
    try:
        db.add_all(
            [
                Game(
                    id=f"game_{10 + index}",
                    master_id=master_id,
                    room_id=room_id,
                    title=f"Нічна гра {index}",
                    system="GURPS",
                    starts_at=datetime(2026, 11, 1, 10, 0) + timedelta(hours=index * 4),
                    duration_minutes=60,
                    max_players=4,
                )
                for index in range(count)
            ]
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture
def conversions(monkeypatch):
    """Журнал ігор, які справді перетворено з рядків БД на об'єкти."""
    seen = []
    original = store.GAMES._to_schema

    def spy(db_obj):
        seen.append(db_obj.id)
        return original(db_obj)

    monkeypatch.setattr(store.GAMES, "_to_schema", spy)
    return seen


@pytest.mark.technical
@pytest.mark.parametrize(
    "query, expected_ids, total, has_more",
    [
        ("room_id=room_1", ["game_1"], 1, False),
        ("master_id=user_1&limit=1", ["game_1"], 2, True),
        ("master_id=user_1&limit=1&offset=1", ["game_2"], 2, False),
        ("offset=50", [], 2, False),
    ],
)
def test_list_games_filters_orders_and_paginates_in_the_database(client, query, expected_ids, total, has_more):
    response = client.get(f"/api/v1/games?{query}")

    assert response.status_code == 200
    body = response.json()
    assert [game["id"] for game in body["items"]] == expected_ids
    assert body["pagination"]["total"] == total
    assert body["pagination"]["has_more"] is has_more


@pytest.mark.technical
def test_list_games_converts_only_the_requested_page(client, conversions):
    add_games(10)

    response = client.get("/api/v1/games?limit=2")

    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 12
    assert len(conversions) == 2


@pytest.mark.technical
def test_busy_game_lookup_loads_only_games_of_that_room_or_master(utc, conversions):
    add_games(10)  # кімната room_3 і майстер user_2: до перевірки room_1 не мають стосунку

    busy = store.find_busy_game(utc(10, 19), 60, room_id="room_1")

    assert busy.id == "game_1"
    assert conversions == ["game_1"]


@pytest.mark.technical
@pytest.mark.parametrize("room_id, expected", [("room_1", True), ("room_3", False)])
def test_room_has_games_checks_the_database_without_loading_games(room_id, expected, conversions):
    assert store.room_has_games(room_id) is expected
    assert conversions == []
