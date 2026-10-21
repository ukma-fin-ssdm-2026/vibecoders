import pytest
from src.api.schemas import Room

def test_room_is_not_full_initially():
    room = Room(id="room_1", name="Зала «Дракон»", capacity=5, is_blocked=False)
    assert room.is_full() is False