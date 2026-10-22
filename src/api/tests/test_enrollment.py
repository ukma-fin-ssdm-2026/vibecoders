from utils import can_enroll_players

def test_can_enroll_players_when_enough_space():
    # max_players=5, current=2, new=2 -> має вистачити місця (True)
    assert can_enroll_players(5, 2, 2) == True