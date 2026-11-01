from datetime import datetime, timezone

from fastapi import APIRouter, Path

from errors import ApiError, error_docs
from models import Enrollment as EnrollmentModel, Game as GameModel, User as UserModel
from schemas import UserBlockPatch, UserDetails, UserGameHistory, UserRole, UserStatus
from security import CurrentUser, require_roles
import store
from store import set_user_blocked

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@router.get(
    "/{user_id}",
    response_model=UserDetails,
    summary="Отримати профіль користувача",
    description=(
        "Профіль із контактами, аватаром та історією записів доступний лише самому користувачу "
        "або власнику клубу. Власник може переглядати й заблоковані профілі."
    ),
    responses=error_docs(400, 401, 403, 404),
)
async def get_user(
    user: CurrentUser,
    user_id: str = Path(..., pattern=r"^user_\d+$", description="Ідентифікатор користувача"),
):
    is_owner = user.role == UserRole.owner
    if not is_owner and user.id != user_id:
        raise ApiError(403, "FORBIDDEN", "Переглядати персональні дані може лише власник клубу або сам користувач")
    db = store.SessionLocal()
    try:
        target = db.query(UserModel).filter(UserModel.id == user_id).first()
        if target is None:
            raise ApiError(404, "USER_NOT_FOUND", f"Користувача {user_id} не знайдено")
        history = (
            db.query(EnrollmentModel, GameModel)
            .join(GameModel, EnrollmentModel.game_id == GameModel.id)
            .filter(EnrollmentModel.player_id == user_id)
            .order_by(GameModel.starts_at, GameModel.id)
            .all()
        )
        return UserDetails(
            id=target.id,
            name=target.name,
            role=target.role,
            is_blocked=target.is_blocked,
            email=target.email,
            contacts=target.contacts,
            avatar_url=target.avatar_url,
            game_history=[
                UserGameHistory(
                    game_id=game.id,
                    title=game.title,
                    starts_at=as_utc(game.starts_at),
                    enrolled_at=as_utc(enrollment.enrolled_at),
                )
                for enrollment, game in history
            ],
        )
    finally:
        db.close()


@router.patch(
    "/{user_id}",
    response_model=UserStatus,
    summary="Заблокувати або розблокувати акаунт",
    description=(
        "Доступно лише власнику клубу. Блокування забороняє вхід і захищені запити, "
        "а також анулює активні токени користувача."
    ),
    responses=error_docs(400, 401, 403, 404, 409),
)
async def patch_user(
    payload: UserBlockPatch,
    user: CurrentUser,
    user_id: str = Path(..., pattern=r"^user_\d+$", description="Ідентифікатор користувача"),
):
    require_roles(user, UserRole.owner)
    if user.id == user_id and payload.is_blocked:
        raise ApiError(409, "CANNOT_BLOCK_SELF", "Власник не може заблокувати власний акаунт")
    updated = set_user_blocked(user_id, payload.is_blocked)
    if updated is None:
        raise ApiError(404, "USER_NOT_FOUND", f"Користувача {user_id} не знайдено")
    public_user, is_blocked = updated
    return UserStatus(
        id=public_user.id,
        name=public_user.name,
        role=public_user.role,
        is_blocked=is_blocked,
    )
