import copy
import itertools
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import store
from main import app


@pytest.fixture(autouse=True)
def isolated_store():
    games = copy.deepcopy(store.GAMES)
    rooms = copy.deepcopy(store.ROOMS)
    enrollments = copy.deepcopy(store.ENROLLMENTS)
    sequence = store._game_sequence
    store._game_sequence = itertools.count(3)
    yield
    store.GAMES.clear()
    store.GAMES.update(games)
    store.ROOMS.clear()
    store.ROOMS.update(rooms)
    store.ENROLLMENTS.clear()
    store.ENROLLMENTS.update(enrollments)
    store._game_sequence = sequence


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def master_headers():
    return {"Authorization": "Bearer master-token"}


@pytest.fixture
def player_headers():
    return {"Authorization": "Bearer player-token"}


@pytest.fixture
def owner_headers():
    return {"Authorization": "Bearer owner-token"}


@pytest.fixture
def game_payload():
    return {
        "title": "Нова кампанія",
        "system": "Pathfinder",
        "room_id": "room_3",
        "starts_at": "2026-11-01T10:00:00Z",
        "duration_minutes": 120,
        "max_players": 4,
    }


@pytest.fixture
def utc():
    def make(day, hour, minute=0):
        return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)

    return make
