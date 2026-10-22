from store import GAMES, GameRecord, next_free_start


def test_free_room_returns_desired_start(utc):
    assert next_free_start("room_3", utc(10, 18), 60) == utc(10, 18)


def test_busy_room_returns_end_of_blocking_game(utc):
    assert next_free_start("room_1", utc(10, 19), 60) == utc(10, 21)


def test_back_to_back_games_are_skipped_until_a_free_slot(utc):
    GAMES["game_9"] = GameRecord(
        id="game_9",
        title="Наступна гра",
        system="D&D 5e",
        room_id="room_1",
        starts_at=utc(10, 21),
        duration_minutes=60,
        max_players=4,
        master_id="user_3",
    )
    assert next_free_start("room_1", utc(10, 19), 60) == utc(10, 22)
