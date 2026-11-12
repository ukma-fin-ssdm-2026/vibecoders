import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import store
from main import app

INTERNAL_DETAIL = "secret-internal-detail"
DB_DETAIL = "unable to open database file"


def database_down(*args, **kwargs):
    raise OperationalError("SELECT 1", {}, Exception(DB_DETAIL))


@pytest.fixture
def tolerant_client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.technical
def test_unexpected_exception_gives_generic_500_and_is_logged(tolerant_client, monkeypatch, caplog):
    def broken_query(*args, **kwargs):
        raise RuntimeError(INTERNAL_DETAIL)

    monkeypatch.setattr("routes.games.query_games", broken_query)

    with caplog.at_level(logging.ERROR, logger="api.errors"):
        response = tolerant_client.get("/api/v1/games")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert INTERNAL_DETAIL not in response.text
    [record] = [r for r in caplog.records if r.name == "api.errors"]
    assert "GET /api/v1/games" in record.getMessage()
    assert isinstance(record.exc_info[1], RuntimeError)
    assert INTERNAL_DETAIL in str(record.exc_info[1])


@pytest.mark.technical
@pytest.mark.parametrize(
    "path, headers_name",
    [("/api/v1/games", None), ("/api/v1/rooms", None), ("/api/v1/users/me", "player_headers")],
)
def test_database_outage_gives_503_with_retry_after_and_no_internals(
    tolerant_client, monkeypatch, caplog, request, path, headers_name
):
    headers = request.getfixturevalue(headers_name) if headers_name else {}
    monkeypatch.setattr(store, "SessionLocal", database_down)

    with caplog.at_level(logging.ERROR, logger="api.errors"):
        response = tolerant_client.get(path, headers=headers)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    body = response.json()["error"]
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert DB_DETAIL not in response.text
    assert any(r.name == "api.errors" and r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.technical
def test_service_recovers_after_database_outage(tolerant_client, monkeypatch):
    monkeypatch.setattr(store, "SessionLocal", database_down)
    assert tolerant_client.get("/api/v1/games").status_code == 503

    monkeypatch.undo()

    response = tolerant_client.get("/api/v1/games")
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 2
