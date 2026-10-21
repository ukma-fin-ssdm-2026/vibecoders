from store import next_free_start


def test_free_room_returns_desired_start(utc):
    assert next_free_start("room_3", utc(10, 18), 60) == utc(10, 18)


def test_busy_room_returns_end_of_blocking_game(utc):
    assert next_free_start("room_1", utc(10, 19), 60) == utc(10, 21)
