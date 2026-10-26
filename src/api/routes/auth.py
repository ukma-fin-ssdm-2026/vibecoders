import math
from datetime import datetime, timezone

from fastapi import APIRouter

from errors import ApiError, error_docs
from schemas import LoginRequest, TokenResponse
from store import (
    CREDENTIALS,
    LOCK_DURATION,
    LOCKED_UNTIL,
    LOGIN_FAILURES,
    LOGIN_WINDOW,
    MAX_FAILED_LOGINS,
    USER_TOKENS,
    USERS,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Увійти в систему",
    description=(
        "Перевіряє пошту та пароль і повертає токен для заголовка Authorization: Bearer. "
        "Демо-акаунти: master@club.test / master-pass-1, player@club.test / player-pass-1, "
        "owner@club.test / owner-pass-1. Повідомлення про помилку однакове для невідомої пошти та хибного пароля. "
        "Після 5 невдалих спроб за 15 хвилин акаунт блокується на 15 хвилин (429, заголовок Retry-After)."
    ),
    responses=error_docs(400, 401, 429),
)
async def login(payload: LoginRequest):
    now = datetime.now(timezone.utc)
    ensure_not_locked(payload.email, now)
    account = CREDENTIALS.get(payload.email)
    if account is None or not verify_password(payload.password, account["password_hash"]):
        register_failed_login(payload.email, now)
        raise ApiError(
            401,
            "INVALID_CREDENTIALS",
            "Невірна пошта або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    LOGIN_FAILURES.pop(payload.email, None)
    user = USERS[account["user_id"]]
    return TokenResponse(access_token=USER_TOKENS[user.id], role=user.role)


def ensure_not_locked(email: str, now: datetime) -> None:
    locked_until = LOCKED_UNTIL.get(email)
    if locked_until is None:
        return
    if now >= locked_until:
        del LOCKED_UNTIL[email]
        return
    retry_after = math.ceil((locked_until - now).total_seconds())
    raise ApiError(
        429,
        "ACCOUNT_LOCKED",
        "Забагато невдалих спроб входу. Спробуйте пізніше",
        headers={"Retry-After": str(retry_after)},
    )


def register_failed_login(email: str, now: datetime) -> None:
    recent = [t for t in LOGIN_FAILURES.get(email, []) if now - t < LOGIN_WINDOW]
    recent.append(now)
    if len(recent) >= MAX_FAILED_LOGINS:
        LOCKED_UNTIL[email] = now + LOCK_DURATION
        LOGIN_FAILURES.pop(email, None)
    else:
        LOGIN_FAILURES[email] = recent
