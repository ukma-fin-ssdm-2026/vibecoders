def can_enroll_players(max_players: int, current_players: int, new_players: int) -> bool:
    if current_players + new_players > max_players:
        return False
    return True