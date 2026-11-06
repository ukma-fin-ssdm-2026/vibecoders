import threading
import time

import pytest
from fastapi.testclient import TestClient

import store
from main import app

WAIT_SECONDS = 0.4


@pytest.mark.technical
@pytest.mark.parametrize(
    "path, headers_name, expected_status",
    [
        ("/api/v1/games/game_1/players/user_2", "player_headers", 204),
        ("/api/v1/games/game_1", "master_headers", 204),
    ],
)
def test_state_changing_requests_wait_for_the_global_lock(request, path, headers_name, expected_status):
    headers = request.getfixturevalue(headers_name)
    client = TestClient(app)
    result = {}

    def send_delete():
        result["response"] = client.delete(path, headers=headers)

    store.db_lock.acquire()
    worker = threading.Thread(target=send_delete)
    try:
        worker.start()
        time.sleep(WAIT_SECONDS)
        assert "response" not in result
    finally:
        store.db_lock.release()
    worker.join(timeout=10)

    assert result["response"].status_code == expected_status


@pytest.mark.technical
def test_parallel_enroll_and_unenroll_do_not_lose_enrollments(owner_headers, player_headers):
    client = TestClient(app)
    results = {}

    def enroll():
        results["enroll"] = client.post("/api/v1/games/game_1/players", headers=owner_headers)

    def unenroll():
        results["unenroll"] = client.delete("/api/v1/games/game_1/players/user_2", headers=player_headers)

    workers = [threading.Thread(target=enroll), threading.Thread(target=unenroll)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert results["enroll"].status_code == 201
    assert results["unenroll"].status_code == 204
    players = client.get("/api/v1/games/game_1/players", headers=owner_headers).json()["players"]
    assert [player["user_id"] for player in players] == ["user_3"]
