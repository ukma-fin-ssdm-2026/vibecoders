import asyncio
import logging

import pytest
from sqlalchemy import create_engine

import db
import main
from db import DEFAULT_DB_TIMEOUT_SECONDS, create_database_engine, read_db_timeout


@pytest.mark.technical
@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, DEFAULT_DB_TIMEOUT_SECONDS),
        ("", DEFAULT_DB_TIMEOUT_SECONDS),
        ("   ", DEFAULT_DB_TIMEOUT_SECONDS),
        ("abc", DEFAULT_DB_TIMEOUT_SECONDS),
        ("0", DEFAULT_DB_TIMEOUT_SECONDS),
        ("-3", DEFAULT_DB_TIMEOUT_SECONDS),
        ("nan", DEFAULT_DB_TIMEOUT_SECONDS),
        ("inf", DEFAULT_DB_TIMEOUT_SECONDS),
        ("0.5", 0.5),
        ("30", 30.0),
    ],
)
def test_db_timeout_setting_falls_back_to_default_on_bad_input(monkeypatch, raw, expected):
    monkeypatch.delenv("DB_TIMEOUT_SECONDS", raising=False)

    assert read_db_timeout(raw) == expected


@pytest.mark.technical
def test_invalid_db_timeout_is_reported_in_the_log(caplog):
    with caplog.at_level(logging.WARNING, logger="api.db"):
        read_db_timeout("abc")

    assert any("DB_TIMEOUT_SECONDS" in record.getMessage() for record in caplog.records)


@pytest.mark.technical
def test_db_timeout_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DB_TIMEOUT_SECONDS", "7")

    assert read_db_timeout() == 7.0


@pytest.mark.technical
def test_sqlite_engine_is_created_with_explicit_timeout(monkeypatch, tmp_path):
    captured = {}

    def capturing_create_engine(url, **kwargs):
        captured.update(kwargs)
        return create_engine(url, **kwargs)

    monkeypatch.setenv("DB_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr(db, "create_engine", capturing_create_engine)

    create_database_engine(f"sqlite:///{tmp_path / 'timeout.db'}")

    assert captured["connect_args"]["timeout"] == 7.0


@pytest.mark.technical
def test_last_free_seat_can_be_taken_and_the_next_player_is_rejected(
    client, master_headers, player_headers, owner_headers, game_payload
):
    game_payload["max_players"] = 2
    created = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    assert created.status_code == 201
    game_id = created.json()["id"]

    assert client.post(f"/api/v1/games/{game_id}/players", headers=player_headers).status_code == 201
    assert client.post(f"/api/v1/games/{game_id}/players", headers=owner_headers).status_code == 201
    overflow = client.post(f"/api/v1/games/{game_id}/players", headers=master_headers)

    assert overflow.status_code == 409
    assert overflow.json()["error"]["code"] == "GAME_FULL"
    assert client.get(f"/api/v1/games/{game_id}").json()["current_players"] == 2


@pytest.mark.technical
@pytest.mark.parametrize(
    "params, expected_status",
    [
        ({"limit": 1}, 200),
        ({"limit": 100}, 200),
        ({"limit": 0}, 400),
        ({"limit": 101}, 400),
        ({"limit": -1}, 400),
        ({"offset": -1}, 400),
        ({"limit": "many"}, 400),
        ({"offset": 10**9}, 200),
    ],
)
def test_list_pagination_boundaries(client, params, expected_status):
    response = client.get("/api/v1/games", params=params)

    assert response.status_code == expected_status
    if expected_status == 400:
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    else:
        assert response.json()["pagination"]["has_more"] is (params.get("limit") == 1)


@pytest.mark.technical
def test_offset_past_the_end_returns_empty_page(client):
    body = client.get("/api/v1/games", params={"offset": 10**9}).json()

    assert body["items"] == []
    assert body["pagination"]["total"] == 2


@pytest.mark.technical
def test_application_starts_when_openapi_file_cannot_be_written(monkeypatch, caplog):
    started = []

    def read_only_filesystem(app):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(main, "seed_db", lambda: None)
    monkeypatch.setattr(main, "save_openapi_spec", read_only_filesystem)

    async def run_lifespan():
        async with main.app.router.lifespan_context(main.app):
            started.append(True)

    with caplog.at_level(logging.WARNING, logger="api.main"):
        asyncio.run(run_lifespan())

    assert started == [True]
    assert any("read-only file system" in record.getMessage() for record in caplog.records)
