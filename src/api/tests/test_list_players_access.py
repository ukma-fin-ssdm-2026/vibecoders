import pytest

from db import SessionLocal
from models import Token, User

@pytest.mark.requirement("US-007", "SEC-002")
def test_list_players_forbidden_for_player_who_does_not_run_the_game(client, player_headers):
    response = client.get("/api/v1/games/game_2/players", headers=player_headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.requirement("US-007")
def test_list_players_allowed_for_master_of_the_game(client, master_headers):
    response = client.get("/api/v1/games/game_2/players", headers=master_headers)

    assert response.status_code == 200
    assert response.json()["max_players"] == 4


@pytest.mark.requirement("US-007", "SEC-002")
def test_list_players_allowed_for_owner(client, owner_headers):
    response = client.get("/api/v1/games/game_2/players", headers=owner_headers)

    assert response.status_code == 200


@pytest.mark.requirement("US-007", "SEC-002")
def test_list_players_forbidden_for_another_master(client):
    session = SessionLocal()
    try:
        session.add(
            User(
                id="user_4",
                email="other-master@club.test",
                password_hash="test-password-hash",
                name="Інший майстер",
                role="master",
            )
        )
        session.add(Token(id="other-master-token", user_id="user_4"))
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/v1/games/game_2/players",
        headers={"Authorization": "Bearer other-master-token"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.requirement("US-007", "SEC-002")
def test_list_players_without_token_returns_401(client):
    response = client.get("/api/v1/games/game_2/players")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.requirement("US-007")
def test_list_players_for_unknown_game_returns_404(client, master_headers):
    response = client.get("/api/v1/games/game_99/players", headers=master_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GAME_NOT_FOUND"
