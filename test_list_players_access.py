import pytest


@pytest.mark.requirement("US-007", "SEC-002")
@pytest.mark.xfail(
    strict=True,
    reason="Дефект D-1: список гравців доступний будь-якому автентифікованому користувачу, а не лише майстру гри",
)
def test_list_players_forbidden_for_player_who_does_not_run_the_game(client, player_headers):
    response = client.get("/api/v1/games/game_2/players", headers=player_headers)

    assert response.status_code == 403


@pytest.mark.requirement("US-007")
def test_list_players_allowed_for_master_of_the_game(client, master_headers):
    response = client.get("/api/v1/games/game_2/players", headers=master_headers)

    assert response.status_code == 200
    assert response.json()["max_players"] == 4
