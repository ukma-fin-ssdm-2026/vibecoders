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
    """Детермінований генератор для перевірки діапазонів і формули full jitter."""

    def __init__(self, fraction: float = 0.5):
        self.fraction = fraction
        self.requested_ranges: List[tuple] = []

    def uniform(self, a: float, b: float) -> float:
        self.requested_ranges.append((a, b))
        return a + (b - a) * self.fraction


@pytest.mark.technical
def test_retry_succeeds_on_transient_failure_after_n_attempts():
    """Тест 1: успіх з другої чи третьої спроби після N тимчасових збоїв."""
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
    # Перша спроба без затримки; 2 повтори мали затримки
    assert all(d >= 0.0 for d in delays)


@pytest.mark.technical
def test_retry_attempts_are_bounded_to_max_attempts():
    """Тест 2: кількість спроб суворо обмежена max_attempts і не зростає нескінченно."""
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
    """Тест 3: після останньої спроби спрацьовує швидка відмова — виняток піднімається,

    а через HTTP це 503 з Retry-After, без витоку деталей; збій залоговано.
    """
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

    # Перевіряємо логування останньої невдачі
    error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("All 3 retry attempts failed" in r.getMessage() for r in error_logs)


@pytest.mark.technical
def test_transient_retry_recovers_http_login(tolerant_client, monkeypatch):
    """Тест 3б: при перехідному збої (1 раз locked, далі успіх) HTTP login успішно повертає 200."""
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
    """Тест 4: невідновні винятки не повторюються — рівно 1 виклик."""
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

    # Жодних затримок не було
    assert len(delays) == 0


@pytest.mark.technical
def test_resilience_helper_coverage_edges():
    """Перевірка допоміжних гілок: пряме декорування без аргументів та is_transient_db_error."""
    assert is_transient_db_error(ValueError("not a db error")) is False

    @retry_with_backoff
    def direct_decorated():
        return 42

    assert direct_decorated() == 42


@pytest.mark.technical
def test_delay_bounds_and_full_jitter_distribution():
    """Тест 5: затримки не перевищують max_delay, лежать у діапазоні [0, min(cap, base*2**n)],

    а при фіксованому rng дають точні очікувані значення; перша спроба без затримки.
    """
    delays: List[float] = []
    base_delay = 0.1
    max_delay = 0.5
    attempts = 0

    def fail_always():
        nonlocal attempts
        attempts += 1
        raise OperationalError("SELECT 1", {}, Exception(BUSY_DETAIL))

    # RNG з фіксованою часткою 1.0 повертає точно максимальну стелю кожного інтервалу
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
    # Очікувані максимальні межі для attempt = 0, 1, 2, 3:
    # 0: min(0.5, 0.1 * 1) = 0.1
    # 1: min(0.5, 0.1 * 2) = 0.2
    # 2: min(0.5, 0.1 * 4) = 0.4
    # 3: min(0.5, 0.1 * 8) = 0.5 (cap!)
    expected_caps = [0.1, 0.2, 0.4, 0.5]
    for d, exp in zip(delays, expected_caps):
        assert d == pytest.approx(exp, abs=1e-6)
        assert d <= max_delay

    # Перевіряємо запитані діапазони uniform(0, cap)
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
    """Тест 6: граничний тест — відхилення некоректних параметрів явною помилкою."""
    with pytest.raises(ValueError) as exc:
        retry_with_backoff(lambda: None, max_attempts=attempts, base_delay=base, max_delay=max_d)
    assert err_msg in str(exc.value)


@pytest.mark.technical
def test_total_max_delay_budget_does_not_exceed_threshold():
    """Тест 7: сумарна затримка між спробами не перевищує 1.5 с при значеннях за замовчуванням.

    Параметри за замовчуванням: max_attempts=3, base_delay=0.05, max_delay=0.5.
    Максимальні затримки (fraction=1.0 — стеля кожного інтервалу):
      - між спробами 1→2: min(0.5, 0.05 * 2^0) = 0.05 с
      - між спробами 2→3: min(0.5, 0.05 * 2^1) = 0.10 с
      - сума: 0.15 с << 1.5 с (границя з запасом).
    Тест підтверджує, що навіть у найгіршому випадку блокування event loop є мінімальним.
    """
    delays: List[float] = []
    max_rng = DeterministicRNG(fraction=1.0)

    def always_failing():
        raise OperationalError("SELECT 1", {}, Exception(LOCKED_DETAIL))

    decorated = retry_with_backoff(
        always_failing,
        max_attempts=3,
        base_delay=0.05,
        max_delay=0.5,
        predicate=is_transient_db_error,
        sleep=delays.append,
        rng=max_rng,
    )

    with pytest.raises(OperationalError):
        decorated()

    # Два інтервали між трьома спробами
    assert len(delays) == 2
    total_delay = sum(delays)
    assert total_delay <= 1.5, f"Сума затримок {total_delay:.4f} с перевищує бюджет 1.5 с"
