"""Модуль надійності: повтори з експоненційним відступом і повним джитером (full jitter).

Композиція з тайм-аутом (§3.5 лекції):
1. Внутрішній рівень: тайм-аут на кожну спробу (DB_TIMEOUT_SECONDS = 10.0 с у конфігурації SQLite).
2. Проміжний рівень: обмежені повтори (max_attempts = 3) з експоненційним відступом і full jitter
   (base_delay = 0.05 с, max_delay = 0.5 с). Загальний бюджет очікування на повтори не перевищує:
   max_attempts * DB_TIMEOUT_SECONDS + sum(delays) <= 3 * 10.0 + 1.5 = 31.5 с.
3. Зовнішній рівень: швидка відмова (fast fail). Після вичерпання спроб виняток піднімається вище
   й обробляється централізованим обробником помилок (HTTP 503 SERVICE_UNAVAILABLE з Retry-After).
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type

from sqlalchemy.exc import OperationalError

logger = logging.getLogger("api.resilience")


def is_transient_db_error(exc: BaseException) -> bool:
    """Визначає, чи є помилка БД тимчасовим збоєм блокування (locked / busy)."""
    if not isinstance(exc, OperationalError):
        return False
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def retry_with_backoff(
    func: Optional[Callable[..., Any]] = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 0.5,
    retry_on: Tuple[Type[BaseException], ...] = (OperationalError,),
    predicate: Optional[Callable[[BaseException], bool]] = None,
    sleep: Optional[Callable[[float], None]] = None,
    rng: Optional[Any] = None,
):
    """Декоратор або функція вищого порядку для повторів з експоненційним відступом і full jitter.

    Формула затримки (Full Jitter):
        delay = rng.uniform(0.0, min(max_delay, base_delay * (2 ** attempt)))
    де attempt = 0 для першого повтору, 1 для другого тощо.
    Перша спроба виконується без жодної затримки.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay < 0:
        raise ValueError("base_delay must be non-negative")
    if max_delay < 0:
        raise ValueError("max_delay must be non-negative")
    if max_delay < base_delay:
        raise ValueError("max_delay must be greater than or equal to base_delay")

    _sleep = sleep if sleep is not None else time.sleep
    _rng = rng if rng is not None else random.SystemRandom()

    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(target)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[BaseException] = None
            for attempt in range(max_attempts):
                try:
                    return target(*args, **kwargs)
                except BaseException as exc:
                    last_exc = exc
                    is_match = isinstance(exc, retry_on)
                    if is_match and predicate is not None:
                        is_match = predicate(exc)

                    # Непідтримувані винятки або остання спроба: не повторюємо
                    if not is_match or attempt == max_attempts - 1:
                        if attempt == max_attempts - 1 and is_match:
                            logger.error(
                                "All %d retry attempts failed for %s. Last error: %s (%s)",
                                max_attempts,
                                getattr(target, "__name__", str(target)),
                                exc.__class__.__name__,
                                exc,
                            )
                        raise

                    cap = min(max_delay, base_delay * (2**attempt))
                    delay = _rng.uniform(0.0, cap)
                    logger.warning(
                        "Retry attempt %d/%d for %s after %.4fs due to %s",
                        attempt + 1,
                        max_attempts,
                        getattr(target, "__name__", str(target)),
                        delay,
                        exc.__class__.__name__,
                    )
                    _sleep(delay)

            if last_exc is not None:
                raise last_exc

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
