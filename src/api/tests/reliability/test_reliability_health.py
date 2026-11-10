import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import store
from main import app

DB_DETAIL = "unable to open database file"


@pytest.fixture
def tolerant_client():
    return TestClient(app, raise_server_exceptions=False)


def database_down(*args, **kwargs):
    raise OperationalError("SELECT 1 FROM users LIMIT 1", {}, Exception(DB_DETAIL))


class BrokenSession:
    closed = False

    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1 FROM users LIMIT 1", {}, Exception(DB_DETAIL))

    def close(self):
        BrokenSession.closed = True


@pytest.mark.technical
def test_health_is_healthy_when_database_responds(tolerant_client):
    response = tolerant_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "checks": {"database": "ok"}}


@pytest.mark.technical
def test_health_needs_no_authorization(tolerant_client):
    assert tolerant_client.get("/api/v1/health", headers={}).status_code == 200


@pytest.mark.technical
def test_health_is_unhealthy_when_database_connection_fails(tolerant_client, monkeypatch, caplog):
    monkeypatch.setattr(store, "SessionLocal", database_down)

    with caplog.at_level(logging.ERROR, logger="api.health"):
        response = tolerant_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json() == {"status": "unhealthy", "checks": {"database": "unavailable"}}
    assert DB_DETAIL not in response.text
    assert any(r.name == "api.health" and r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.technical
def test_health_is_unhealthy_when_query_fails_and_session_is_closed(tolerant_client, monkeypatch):
    BrokenSession.closed = False
    monkeypatch.setattr(store, "SessionLocal", BrokenSession)

    response = tolerant_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"
    assert BrokenSession.closed is True


@pytest.mark.technical
def test_health_recovers_after_database_outage(tolerant_client, monkeypatch):
    monkeypatch.setattr(store, "SessionLocal", database_down)
    assert tolerant_client.get("/api/v1/health").status_code == 503

    monkeypatch.undo()

    response = tolerant_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.technical
def test_health_does_not_hide_programming_errors(tolerant_client, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("bug in session factory")

    monkeypatch.setattr(store, "SessionLocal", broken)

    response = tolerant_client.get("/api/v1/health")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
