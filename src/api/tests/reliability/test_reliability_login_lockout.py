"""R-09: лічильник невдалих входів зберігається в БД і оновлюється атомарно."""

import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import store
from main import app
from models import LoginFailure, User

EMAIL = "master@club.test"
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def failure_rows(email=None):
    db = store.SessionLocal()
    try:
        query = db.query(LoginFailure)
        if email is not None:
            query = query.filter(LoginFailure.email == email)
        return query.count()
    finally:
        db.close()


def add_failure_row(email, failed_at):
    db = store.SessionLocal()
    try:
        db.add(LoginFailure(email=email, failed_at=failed_at.replace(tzinfo=None)))
        db.commit()
    finally:
        db.close()


def locked_until_in_db(email=EMAIL):
    db = store.SessionLocal()
    try:
        return db.query(User.locked_until).filter(User.email == email).scalar()
    finally:
        db.close()


@pytest.mark.technical
def test_failed_logins_are_stored_in_the_database(client):
    for _ in range(3):
        response = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-pass-1"})
        assert response.status_code == 401

    assert failure_rows(EMAIL) == 3
    # той самий стан бачить будь-який інший екземпляр проксі (інший воркер або перезапущений процес)
    assert len(store.LoginFailuresProxy().get(EMAIL)) == 3


@pytest.mark.technical
def test_lockout_is_persisted_and_failure_rows_are_cleared(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-pass-1"})

    assert locked_until_in_db() is not None
    assert failure_rows(EMAIL) == 0
    response = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "master-pass-1"})
    assert response.status_code == 429


@pytest.mark.technical
def test_parallel_failed_logins_are_all_counted():
    results = []

    def attempt():
        results.append(store.record_failed_login(EMAIL, NOW))

    workers = [threading.Thread(target=attempt) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=20)

    assert len(results) == 8
    # п'ята спроба блокує акаунт й скидає лічильник, ще три спроби створюють нові записи
    assert results.count(True) == 1
    assert failure_rows(EMAIL) == 3
    assert locked_until_in_db() is not None


@pytest.mark.technical
def test_counter_write_failure_rolls_back_everything_and_is_raised(monkeypatch):
    add_failure_row(EMAIL, NOW - timedelta(minutes=30))  # прострочений запис, який транзакція мала б видалити
    real_session_factory = store.SessionLocal

    def session_whose_insert_fails():
        session = real_session_factory()

        def broken_flush(*args, **kwargs):
            raise OperationalError("INSERT INTO login_failures", {}, Exception("disk I/O error"))

        session.flush = broken_flush
        return session

    monkeypatch.setattr(store, "SessionLocal", session_whose_insert_fails)
    with pytest.raises(OperationalError):
        store.record_failed_login(EMAIL, NOW)
    monkeypatch.setattr(store, "SessionLocal", real_session_factory)

    # «все або нічого»: видалення прострочених записів теж відкочено, блокування не виставлено
    assert failure_rows(EMAIL) == 1
    assert locked_until_in_db() is None


@pytest.mark.technical
def test_login_fails_fast_with_503_when_failed_attempt_cannot_be_recorded(monkeypatch):
    def database_down(*args, **kwargs):
        raise OperationalError("INSERT INTO login_failures", {}, Exception("unable to open database file"))

    monkeypatch.setattr("routes.auth.record_failed_login", database_down)
    tolerant_client = TestClient(app, raise_server_exceptions=False)

    response = tolerant_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-pass-1"})

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert "unable to open database file" not in response.text


@pytest.mark.technical
def test_only_failures_inside_the_window_are_counted_and_expired_rows_are_pruned():
    edge = NOW - store.LOGIN_WINDOW  # рівно 15 хвилин тому: вже поза вікном
    add_failure_row("other@club.test", NOW - timedelta(hours=2))
    add_failure_row(EMAIL, edge)
    add_failure_row(EMAIL, edge + timedelta(seconds=1))

    assert store.record_failed_login(EMAIL, NOW) is False

    assert failure_rows("other@club.test") == 0
    assert failure_rows(EMAIL) == 2  # запис на межі вікна видалено; лишилися «майже межа» й нова спроба
