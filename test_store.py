from datetime import timedelta

import pytest

import store
from store import (
    ENROLLMENTS,
    GAMES,
    find_busy_game,
    hash_password,
    next_game_id,
    sorted_games,
    time_overlap,
    to_game,
    verify_password,
)


@pytest.mark.requirement("US-002")
def test_time_overlap_detects_partial_intersection(utc):
    assert time_overlap(utc(10, 18), 180, utc(10, 20), 60) is True


@pytest.mark.requirement("US-002")
def test_time_overlap_is_symmetric(utc):
    assert time_overlap(utc(10, 20), 60, utc(10, 18), 180) is True


@pytest.mark.requirement("US-002")
def test_time_overlap_back_to_back_slots_do_not_overlap(utc):
    assert time_overlap(utc(10, 18), 180, utc(10, 21), 60) is False


@pytest.mark.requirement("US-002")
def test_time_overlap_one_minute_intersection_counts(utc):
    assert time_overlap(utc(10, 18), 181, utc(10, 21), 60) is True


@pytest.mark.requirement("US-002")
def test_time_overlap_contained_slot(utc):
    assert time_overlap(utc(10, 12), 600, utc(10, 14), 30) is True


@pytest.mark.requirement("US-002")
def test_time_overlap_far_apart_days(utc):
    assert time_overlap(utc(10, 18), 180, utc(12, 18), 180) is False


@pytest.mark.requirement("US-002")
def test_find_busy_game_returns_game_in_same_room(utc):
    busy = find_busy_game(utc(10, 19), 60, room_id="room_1")
    assert busy is GAMES["game_1"]


@pytest.mark.requirement("US-002", "REL-002")
def test_find_busy_game_returns_game_of_same_master(utc):
    busy = find_busy_game(utc(11, 17), 60, master_id="user_1")
    assert busy is GAMES["game_2"]


@pytest.mark.requirement("US-002")
def test_find_busy_game_returns_none_for_free_slot(utc):
    assert find_busy_game(utc(20, 10), 60, room_id="room_1", master_id="user_1") is None


@pytest.mark.requirement("US-002")
def test_find_busy_game_ignores_other_room(utc):
    assert find_busy_game(utc(10, 19), 60, room_id="room_3") is None


@pytest.mark.requirement("US-002")
def test_find_busy_game_without_filters_never_conflicts(utc):
    assert find_busy_game(utc(10, 19), 60) is None


@pytest.mark.requirement("US-002")
def test_find_busy_game_respects_exclusion_of_edited_game(utc):
    assert find_busy_game(utc(10, 18), 180, room_id="room_1", exclude_game_id="game_1") is None


@pytest.mark.requirement("US-002")
def test_find_busy_game_returns_earliest_of_several_conflicts(utc):
    first = find_busy_game(utc(10, 0), 3000, master_id="user_1")
    assert first is GAMES["game_1"]


@pytest.mark.requirement("US-006")
def test_sorted_games_orders_by_start_time_then_id(utc):
    later = GAMES["game_2"].model_copy(update={"id": "game_0", "starts_at": GAMES["game_1"].starts_at})
    ordered = sorted_games([GAMES["game_2"], GAMES["game_1"], later])
    assert [g.id for g in ordered] == ["game_0", "game_1", "game_2"]


@pytest.mark.requirement("US-006")
def test_sorted_games_empty_list():
    assert sorted_games([]) == []


@pytest.mark.requirement("US-002")
def test_next_game_id_increments_sequence():
    assert next_game_id() == "game_3"
    assert next_game_id() == "game_4"


@pytest.mark.requirement("US-001")
def test_to_game_counts_enrolled_players():
    assert to_game(GAMES["game_1"]).current_players == 1
    assert to_game(GAMES["game_2"]).current_players == 0


@pytest.mark.requirement("US-001")
def test_to_game_without_enrollment_entry_gives_zero():
    ENROLLMENTS.pop("game_2")
    assert to_game(GAMES["game_2"]).current_players == 0


@pytest.mark.requirement("SEC-001")
def test_hash_password_is_deterministic_and_hex():
    first = hash_password("secret-pass")
    assert first == hash_password("secret-pass")
    assert len(first) == 64
    int(first, 16)


@pytest.mark.requirement("SEC-001")
def test_hash_password_differs_for_different_passwords():
    assert hash_password("secret-pass") != hash_password("secret-pasS")


@pytest.mark.requirement("SEC-001")
def test_verify_password_accepts_correct_and_rejects_wrong():
    stored = hash_password("master-pass-1")
    assert verify_password("master-pass-1", stored) is True
    assert verify_password("master-pass-2", stored) is False


@pytest.mark.requirement("SEC-001")
def test_verify_password_uses_constant_time_compare(monkeypatch):
    calls = []

    def fake_compare(a, b):
        calls.append((a, b))
        return True

    monkeypatch.setattr(store.hmac, "compare_digest", fake_compare)
    assert verify_password("any", "stored-hash") is True
    assert len(calls) == 1
    assert calls[0][1] == "stored-hash"


@pytest.mark.parametrize(
    "minutes_a, minutes_b, expected",
    [(60, 60, True), (1, 1, True), (1, 0, False)],
)
@pytest.mark.requirement("US-002")
def test_time_overlap_same_start_boundaries(utc, minutes_a, minutes_b, expected):
    assert time_overlap(utc(10, 18), minutes_a, utc(10, 18), minutes_b) is expected


@pytest.mark.requirement("US-002")
def test_time_overlap_end_boundary_is_exclusive(utc):
    start = utc(10, 18)
    assert time_overlap(start, 60, start + timedelta(minutes=60), 60) is False


@pytest.mark.requirement("US-002")
def test_find_busy_game_skips_excluded_game_and_still_finds_later_conflict(utc):
    busy = find_busy_game(utc(10, 18), 2000, master_id="user_1", exclude_game_id="game_1")
    assert busy is GAMES["game_2"]


@pytest.mark.requirement("US-002", "REL-002")
def test_find_busy_game_ignores_games_of_other_master(utc):
    assert find_busy_game(utc(10, 19), 60, master_id="user_99") is None
