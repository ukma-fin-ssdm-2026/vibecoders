from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from schemas import GameBase
from store import hash_password, time_overlap, verify_password

moments = st.datetimes(
    min_value=datetime(2026, 1, 1),
    max_value=datetime(2027, 12, 31),
    timezones=st.just(timezone.utc),
)
durations = st.integers(min_value=1, max_value=1440)


@given(moments, durations, moments, durations)
def test_time_overlap_is_symmetric_for_any_slots(start_a, minutes_a, start_b, minutes_b):
    assert time_overlap(start_a, minutes_a, start_b, minutes_b) == time_overlap(start_b, minutes_b, start_a, minutes_a)


@given(moments, durations)
def test_slot_always_overlaps_itself(start, minutes):
    assert time_overlap(start, minutes, start, minutes) is True


@given(moments, durations, durations)
def test_back_to_back_slots_never_overlap(start, minutes_a, minutes_b):
    following = start + timedelta(minutes=minutes_a)
    assert time_overlap(start, minutes_a, following, minutes_b) is False


@given(moments, durations, st.integers(min_value=1, max_value=1440))
def test_slot_starting_inside_another_always_overlaps(start, minutes, offset):
    inside = start + timedelta(minutes=offset % minutes)
    assert time_overlap(start, minutes, inside, 1) is True


@given(st.integers(min_value=30, max_value=720), st.integers(min_value=2, max_value=8))
def test_game_base_accepts_every_value_in_documented_range(duration, players):
    game = GameBase(
        title="Гра",
        system="D&D",
        room_id="room_1",
        starts_at="2026-10-10T18:00:00Z",
        duration_minutes=duration,
        max_players=players,
    )
    assert (game.duration_minutes, game.max_players) == (duration, players)


@given(st.one_of(st.integers(max_value=29), st.integers(min_value=721)))
def test_game_base_rejects_every_duration_outside_range(duration):
    with pytest.raises(ValidationError):
        GameBase(
            title="Гра",
            system="D&D",
            room_id="room_1",
            starts_at="2026-10-10T18:00:00Z",
            duration_minutes=duration,
            max_players=4,
        )


@settings(deadline=None, max_examples=15)
@given(st.text(min_size=1, max_size=40))
def test_password_hash_verifies_only_original(password):
    stored = hash_password(password)
    assert verify_password(password, stored) is True
    assert verify_password(password + "x", stored) is False
