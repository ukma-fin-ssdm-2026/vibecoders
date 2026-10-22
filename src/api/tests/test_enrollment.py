from utils import can_enroll_players

def test_can_enroll_players_when_enough_space():
    # max_players=5, current=2, new=2 -> має вистачити місця (True)
    assert can_enroll_players(5, 2, 2) == True

def test_cannot_enroll_when_space_exceeded():
    # max_players=4, поточних=3, нових=2 -> 3+2=5 (більше 4), тому False
    assert can_enroll_players(4, 3, 2) == False    