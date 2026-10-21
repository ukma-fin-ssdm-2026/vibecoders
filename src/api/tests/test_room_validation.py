import pytest
from src.api.schemas import Room

def test_room_is_not_full_initially():
    room = Room(id="room_1", name="Зала «Дракон»", capacity=5, is_blocked=False)
    assert room.is_full() is False

def test_room_is_full_when_capacity_reached():
    room = Room(id="room_1", name="Зала «Дракон»", capacity=2, is_blocked=False, current_players=2)
    assert room.is_full() is True

def test_room_exceeds_capacity():
    room = Room(id="room_1", name="Зала «Дракон»", capacity=3, is_blocked=False, current_players=5)
    assert room.is_full() is True