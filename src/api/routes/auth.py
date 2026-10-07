from fastapi import APIRouter

from errors import ApiError, error_docs
from schemas import LoginRequest, TokenResponse
from store import CREDENTIALS, USER_TOKENS, USERS, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Увійти в систему",
    description=(
        "Перевіряє пошту та пароль і повертає токен для заголовка Authorization: Bearer. "
        "Демо-акаунти: master@club.test / master-pass-1, player@club.test / player-pass-1, "
        "owner@club.test / owner-pass-1. Повідомлення про помилку однакове для невідомої пошти та хибного пароля."
    ),
    responses=error_docs(400, 401),
)
async def login(payload: LoginRequest):
    account = CREDENTIALS.get(payload.email)
    if account is None or not verify_password(payload.password, account["password_hash"]):
        raise ApiError(401, "INVALID_CREDENTIALS", "Невірна пошта або пароль", headers={"WWW-Authenticate": "Bearer"})
    user = USERS[account["user_id"]]
    return TokenResponse(access_token=USER_TOKENS[user.id], role=user.role)
