"""R-08: блокувальні обробники не виконуються в потоці подій.

FastAPI запускає звичайні `def`-обробники в пулі потоків, а `async def` без `await` блокує увесь цикл подій.
"""

import asyncio
import inspect

import pytest
from fastapi.routing import APIRoute

from main import app


def running_on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


@pytest.mark.technical
def test_no_api_handler_is_a_coroutine_function():
    routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/v1")]

    assert len(routes) >= 20
    coroutine_handlers = [
        f"{sorted(route.methods)} {route.path}" for route in routes if inspect.iscoroutinefunction(route.endpoint)
    ]
    assert coroutine_handlers == []


@pytest.mark.technical
def test_password_verification_runs_outside_the_event_loop(client, monkeypatch):
    seen = []

    def spy(password, password_hash):
        seen.append(running_on_event_loop())
        return True

    monkeypatch.setattr("routes.auth.verify_password", spy)

    response = client.post("/api/v1/auth/login", json={"email": "player@club.test", "password": "player-pass-1"})

    assert response.status_code == 200
    assert seen == [False]


@pytest.mark.technical
def test_password_hashing_on_registration_runs_outside_the_event_loop(client, monkeypatch):
    seen = []

    def spy(password):
        seen.append(running_on_event_loop())
        return "stub-hash"

    monkeypatch.setattr("store.hash_password", spy)

    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Нова", "email": "new-player@club.test", "password": "new-pass-1234"},
    )

    assert response.status_code == 201
    assert seen == [False]
