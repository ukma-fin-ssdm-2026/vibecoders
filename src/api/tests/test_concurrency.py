import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.mark.requirement("REL-001", "REL-002")
def test_concurrent_game_creation(isolated_store):
    """
    Тестує конкурентне створення гри.
    20 потоків одночасно намагаються зайняти один слот.
    Очікуємо рівно одну успішну відповідь (201) і 19 конфліктів (409).
    """
    payload = {
        "title": "Конкурентна гра",
        "system": "D&D",
        "room_id": "room_1",
        "starts_at": "2026-11-01T10:00:00Z",
        "duration_minutes": 120,
        "max_players": 4,
    }
    headers = {"Authorization": "Bearer master-token"}

    def create_game():
        return client.post("/api/v1/games", json=payload, headers=headers)

    # Запускаємо 20 потоків одночасно
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(create_game) for _ in range(20)]
        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    status_codes = [r.status_code for r in responses]

    # Перевіряємо вимоги надійності
    assert status_codes.count(201) == 1
    assert status_codes.count(409) == 19
