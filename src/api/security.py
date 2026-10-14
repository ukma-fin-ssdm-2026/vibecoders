from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from errors import ApiError
from schemas import User, UserRole
from store import TOKENS, USERS

bearer_scheme = HTTPBearer(
    auto_error=False,
    description=(
        "Демо-токени: master-token (майстер), "
        "player-token (гравець), owner-token (власник клубу)"
    ),
)


def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
) -> User:
    if credentials is None or credentials.credentials not in TOKENS:
        raise ApiError(
            401,
            "UNAUTHORIZED",
            "Відсутній або недійсний токен доступу",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return USERS[TOKENS[credentials.credentials]]


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(user: User, *roles: UserRole) -> None:
    if user.role not in roles:
        raise ApiError(403, "FORBIDDEN", "Ваша роль не дозволяє виконати цю дію")
