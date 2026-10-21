from store import next_free_start


def test_free_room_returns_desired_start(utc):
    assert next_free_start("room_3", utc(10, 18), 60) == utc(10, 18)
