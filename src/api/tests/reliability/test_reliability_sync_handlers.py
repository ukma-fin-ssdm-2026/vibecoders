"""R-08: блокувальні обробники не виконуються в потоці подій.

FastAPI запускає звичайні `def`-обробники в пулі потоків, а `async def` без `await` блокує увесь цикл подій.
"""

import asyncio
import inspect

import pytest

from routes import auth, games, health, notifications, rooms, users

ROUTE_MODULES = [auth, games, health, notifications, rooms, users]


def running_on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


@pytest.mark.technical
def test_no_route_module_defines_a_coroutine_function():
    # Перевірка за модулями, а не за app.routes: вона не залежить від того, як версія FastAPI зберігає маршрути.
    defined_functions = 0
    coroutines = []
    for module in ROUTE_MODULES:
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if function.__module__ != module.__name__:
                continue
            defined_functions += 1
            if inspect.iscoroutinefunction(function):
                coroutines.append(f"{module.__name__}.{name}")

    assert defined_functions >= 20
    assert coroutines == []


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
