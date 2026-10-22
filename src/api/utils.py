def can_enroll_players(max_players: int, current_players: int, new_players: int) -> bool:
    """Checks if a game has enough space for new players."""
    return current_players + new_players <= max_players
