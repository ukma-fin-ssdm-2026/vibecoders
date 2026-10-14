from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_or_docs():
    """Перевірка доступності Open API специфікації"""
    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_login_success():
    """Тест успішного входу під демо-акаунтом"""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "master@club.test", "password": "master-pass-1"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_get_games_public():
    """Тест отримання списку ігор без токена (публічний доступ -> 200)"""
    response = client.get("/api/v1/games")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data


def test_get_games_authorized():
    """Тест отримання списку ігор з валідним токеном (200)"""
    response = client.get(
        "/api/v1/games",
        headers={"Authorization": "Bearer player-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data