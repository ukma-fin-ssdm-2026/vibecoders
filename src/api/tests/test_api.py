import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
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
        json={"email": "master@club.test", "password": "master-pass-1"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_get_games():
    """Тест отримання списку ігор"""
    response = client.get("/api/v1/games")
    assert response.status_code in [200, 401]