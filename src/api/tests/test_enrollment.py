from utils import can_enroll_players


def test_can_enroll_players_when_enough_space():
    assert can_enroll_players(5, 2, 2)


def test_cannot_enroll_when_space_exceeded():
    assert not can_enroll_players(4, 3, 2)
