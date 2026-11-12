import logging
from typing import List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from main import app
from resilience import is_transient_db_error, retry_with_backoff
import store

LOCKED_DETAIL = "database is locked"
BUSY_DETAIL = "sqlite3.OperationalError: database is busy"


@pytest.fixture
def tolerant_client():
    return TestClient(app, raise_server_exceptions=False)


class DeterministicRNG:
    def __init__(self, fraction: float = 0.5):
        self.fraction = fraction
        self.requested_ranges: List[tuple] = []

    def uniform(self, a: float, b: float) -> float:
        self.requested_ranges.append((a, b))
        return a + (b - a) * self.fraction


@pytest.mark.technical
def test_retry_succeeds_on_transient_failure_after_n_attempts():
    call_count = 0
    delays: List[float] = []

    def transient_action():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OperationalError("SELECT 1", {}, Exception(LOCKED_DETAIL))
        return "success_payload"

    rng = DeterministicRNG(fraction=0.5)
    decorated = retry_with_backoff(
        transient_action,
        max_attempts=4,
        base_delay=0.1,
        max_delay=1.0,
        predicate=is_transient_db_error,
        sleep=delays.append,
        rng=rng,
    )

    result = decorated()

    assert result == "success_payload"
    assert call_count == 3
    assert len(delays) == 2
    assert all(d >= 0.0 for d in delays)


@pytest.mark.technical
def test_retry_attempts_are_bounded_to_max_attempts():
    call_count = 0
    delays: List[float] = []

    def always_failing_action():
        nonlocal call_count
        call_count += 1
        raise OperationalError("SELECT 1", {}, Exception(LOCKED_DETAIL))

    rng = DeterministicRNG(fraction=0.5)
    decorated = retry_with_backoff(
        always_failing_action,
        max_attempts=3,
        base_delay=0.1,
        max_delay=0.8,
        predicate=is_transient_db_error,
        sleep=delays.append,
        rng=rng,
    )

    with pytest.raises(OperationalError) as exc_info:
        decorated()

    assert LOCKED_DETAIL in str(exc_info.value)
    assert call_count == 3
    assert len(delays) == 2


@pytest.mark.technical
def test_reaction_after_exhausted_retries_raises_and_http_returns_503(tolerant_client, monkeypatch, caplog):
    call_attempts = 0

    def locked_fetch(email: str):
        nonlocal call_attempts
        call_attempts += 1
        raise OperationalError("SELECT user", {}, Exception(LOCKED_DETAIL))

    monkeypatch.setattr(
        store.CREDENTIALS,
        "_fetch_with_retry",
        retry_with_backoff(
            locked_fetch,
            max_attempts=3,
            base_delay=0.001,
            max_delay=0.01,
            predicate=is_transient_db_error,
            sleep=lambda _: None,
        ),
    )

    with caplog.at_level(logging.ERROR):
        response = tolerant_client.post(
            "/api/v1/auth/login",
            json={"email": "master@club.test", "password": "master-pass-1"},
        )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    body = response.json()
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert LOCKED_DETAIL not in response.text
    assert call_attempts == 3

    error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("All 3 retry attempts failed" in r.getMessage() for r in error_logs)


@pytest.mark.technical
def test_transient_retry_recovers_http_login(tolerant_client, monkeypatch):
    call_attempts = 0
    real_fetch = store._fetch_credentials

    def flakey_fetch(email: str):
        nonlocal call_attempts
        call_attempts += 1
        if call_attempts == 1:
            raise OperationalError("SELECT user", {}, Exception(LOCKED_DETAIL))
        return real_fetch(email)

    monkeypatch.setattr(
        store.CREDENTIALS,
        "_fetch_with_retry",
        retry_with_backoff(
            flakey_fetch,
            max_attempts=3,
            base_delay=0.001,
            max_delay=0.01,
            predicate=is_transient_db_error,
            sleep=lambda _: None,
        ),
    )

    response = tolerant_client.post(
        "/api/v1/auth/login",
        json={"email": "master@club.test", "password": "master-pass-1"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "master-token"
    assert call_attempts == 2


@pytest.mark.technical
def test_non_retryable_exceptions_fail_fast_without_retries():
    calls_runtime = 0
    calls_non_transient = 0
    delays: List[float] = []

    def failing_runtime():
        nonlocal calls_runtime
        calls_runtime += 1
        raise RuntimeError("programming bug")

    def failing_non_transient_db():
        nonlocal calls_non_transient
        calls_non_transient += 1
        raise OperationalError("SELECT", {}, Exception("no such table: missing"))

    decorated_runtime = retry_with_backoff(
        failing_runtime,
        max_attempts=3,
        predicate=is_transient_db_error,
        sleep=delays.append,
    )
    decorated_db = retry_with_backoff(
        failing_non_transient_db,
        max_attempts=3,
        predicate=is_transient_db_error,
        sleep=delays.append,
    )

    with pytest.raises(RuntimeError):
        decorated_runtime()
    assert calls_runtime == 1

    with pytest.raises(OperationalError):
        decorated_db()
    assert calls_non_transient == 1

    assert len(delays) == 0


@pytest.mark.technical
@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
def test_process_control_exceptions_are_not_retried(exception_type):
    calls = 0
    delays = []

    def interrupt():
        nonlocal calls
        calls += 1
        raise exception_type()

    decorated = retry_with_backoff(interrupt, sleep=delays.append)

    with pytest.raises(exception_type):
        decorated()

    assert calls == 1
    assert delays == []


@pytest.mark.technical
def test_resilience_helper_coverage_edges():
    assert is_transient_db_error(ValueError("not a db error")) is False

    @retry_with_backoff
    def direct_decorated():
        return 42

    assert direct_decorated() == 42


@pytest.mark.technical
def test_delay_bounds_and_full_jitter_distribution():
    delays: List[float] = []
    base_delay = 0.1
    max_delay = 0.5
    attempts = 0

    def fail_always():
        nonlocal attempts
        attempts += 1
        raise OperationalError("SELECT 1", {}, Exception(BUSY_DETAIL))

    max_rng = DeterministicRNG(fraction=1.0)
    decorated = retry_with_backoff(
        fail_always,
        max_attempts=5,
        base_delay=base_delay,
        max_delay=max_delay,
        predicate=is_transient_db_error,
        sleep=delays.append,
        rng=max_rng,
    )

    with pytest.raises(OperationalError):
        decorated()

    assert attempts == 5
    assert len(delays) == 4
    expected_caps = [0.1, 0.2, 0.4, 0.5]
    for d, exp in zip(delays, expected_caps):
        assert d == pytest.approx(exp, abs=1e-6)
        assert d <= max_delay

    for requested, exp in zip(max_rng.requested_ranges, expected_caps):
        assert requested[0] == 0.0
        assert requested[1] == pytest.approx(exp, abs=1e-6)


@pytest.mark.technical
@pytest.mark.parametrize(
    "attempts, base, max_d, err_msg",
    [
        (0, 0.1, 1.0, "max_attempts must be at least 1"),
        (-2, 0.1, 1.0, "max_attempts must be at least 1"),
        (3, -0.01, 1.0, "base_delay must be non-negative"),
        (3, 0.1, -0.5, "max_delay must be non-negative"),
        (3, 1.0, 0.5, "max_delay must be greater than or equal to base_delay"),
    ],
)
def test_invalid_parameters_rejected(attempts, base, max_d, err_msg):
    with pytest.raises(ValueError) as exc:
        retry_with_backoff(lambda: None, max_attempts=attempts, base_delay=base, max_delay=max_d)
    assert err_msg in str(exc.value)
