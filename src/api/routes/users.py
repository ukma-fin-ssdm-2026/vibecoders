from datetime import datetime, timezone

from fastapi import APIRouter, Path, Query

from errors import ApiError, error_docs
from models import Enrollment as EnrollmentModel, Game as GameModel, User as UserModel
from schemas import (
    Pagination,
    UserBlockPatch,
    UserDetails,
    UserGameHistory,
    UserListResponse,
    UserProfilePatch,
    UserRole,
    UserStatus,
)
from security import CurrentUser, require_roles
import store
from store import set_user_blocked

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def user_details(db, target: UserModel) -> UserDetails:
    history = (
        db.query(EnrollmentModel, GameModel)
        .join(GameModel, EnrollmentModel.game_id == GameModel.id)
        .filter(EnrollmentModel.player_id == target.id)
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


@router.get(
    "",
    response_model=UserListResponse,
    summary="Отримати список користувачів",
    description="Повертає список користувачів із пагінацією. Доступно лише власнику клубу.",
    responses=error_docs(400, 401, 403),
)
async def list_users(
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100, description="Максимальна кількість користувачів у відповіді"),
    offset: int = Query(0, ge=0, description="Скільки користувачів пропустити"),
):
    require_roles(user, UserRole.owner)
    db = store.SessionLocal()
    try:
        query = db.query(UserModel).order_by(UserModel.id)
        total = query.count()
        users = query.offset(offset).limit(limit).all()
        return UserListResponse(
            items=[
                UserStatus(id=item.id, name=item.name, role=item.role, is_blocked=item.is_blocked) for item in users
            ],
            pagination=Pagination(
                limit=limit,
                offset=offset,
                total=total,
                has_more=offset + limit < total,
            ),
        )
    finally:
        db.close()


@router.get(
    "/me",
    response_model=UserDetails,
    summary="Отримати власний профіль",
    description="Повертає профіль поточного користувача, включно з контактами, аватаром та історією записів.",
    responses=error_docs(401, 403, 404),
)
async def get_my_profile(user: CurrentUser):
    db = store.SessionLocal()
    try:
        target = db.query(UserModel).filter(UserModel.id == user.id).first()
        if target is None:
            raise ApiError(404, "USER_NOT_FOUND", "Профіль користувача не знайдено")
        return user_details(db, target)
    finally:
        db.close()


@router.patch(
    "/me",
    response_model=UserDetails,
    summary="Оновити власний профіль",
    description=(
        "Поточний користувач може змінити ім'я, контакти та URL аватара. "
        "Передане null очищує контакти або аватар; ім'я не може бути порожнім."
    ),
    responses=error_docs(400, 401, 403, 404),
)
async def patch_my_profile(payload: UserProfilePatch, user: CurrentUser):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ApiError(400, "VALIDATION_ERROR", "Передайте хоча б одне поле для оновлення")
    if "name" in changes and changes["name"] is None:
        raise ApiError(400, "VALIDATION_ERROR", "Ім'я не може бути null")

    db = store.SessionLocal()
    try:
        target = db.query(UserModel).filter(UserModel.id == user.id).first()
        if target is None:
            raise ApiError(404, "USER_NOT_FOUND", "Профіль користувача не знайдено")
        for field, value in changes.items():
            setattr(target, field, value)
        db.commit()
        db.refresh(target)
        store.USERS._cache.pop(user.id, None)
        return user_details(db, target)
    finally:
        db.close()


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
        return user_details(db, target)
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
