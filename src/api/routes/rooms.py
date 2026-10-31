from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Path, Query, Response
from pydantic import AwareDatetime

from errors import ApiError, error_docs
from schemas import (
    Booking,
    CalendarResponse,
    CalendarRoom,
    Pagination,
    Room,
    RoomBlockCreate,
    RoomBlockResponse,
    RoomBookingsResponse,
    RoomListResponse,
    RoomPatch,
    UserRole,
)
from security import CurrentUser, require_roles
from models import Enrollment as EnrollmentModel, Game as GameModel, RoomBlock as RoomBlockModel
from notifications import notify_game_cancelled
from schemas import Player
import store
from store import GAMES, ROOMS, db_lock, sorted_games

router = APIRouter(prefix="/api/v1/rooms", tags=["Rooms"])


def get_room_or_404(room_id: str) -> Room:
    room = ROOMS.get(room_id)
    if room is None:
        raise ApiError(404, "ROOM_NOT_FOUND", f"Кімнату {room_id} не знайдено")
    return room


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def block_response(block: RoomBlockModel) -> RoomBlockResponse:
    return RoomBlockResponse(
        id=block.id,
        room_id=block.room_id,
        starts_at=as_utc(block.starts_at),
        ends_at=as_utc(block.ends_at),
    )


def room_blocks(room_id: str) -> List[RoomBlockResponse]:
    db = store.SessionLocal()
    try:
        blocks = (
            db.query(RoomBlockModel)
            .filter(RoomBlockModel.room_id == room_id)
            .order_by(RoomBlockModel.starts_at, RoomBlockModel.id)
            .all()
        )
        return [block_response(block) for block in blocks]
    finally:
        db.close()


@router.get(
    "",
    response_model=RoomListResponse,
    summary="Отримати список кімнат",
    description="Повертає кімнати клубу з пагінацією. Кімнати відсортовані за id.",
    responses=error_docs(400),
)
async def list_rooms(
    limit: int = Query(20, ge=1, le=100, description="Максимальна кількість кімнат у відповіді"),
    offset: int = Query(0, ge=0, description="Скільки кімнат пропустити"),
):
    rooms: List[Room] = sorted(ROOMS.values(), key=lambda room: room.id)
    return RoomListResponse(
        items=rooms[offset : offset + limit],
        pagination=Pagination(
            limit=limit,
            offset=offset,
            total=len(rooms),
            has_more=offset + limit < len(rooms),
        ),
    )


@router.get(
    "/calendar",
    response_model=CalendarResponse,
    summary="Отримати календар усіх кімнат",
    description=(
        "Повертає бронювання та періоди блокування для всіх кімнат клубу. "
        "Параметри starts_at і ends_at задають необов'язковий спільний часовий інтервал."
    ),
    responses=error_docs(400),
)
async def get_calendar(
    starts_at: AwareDatetime = Query(None, description="Початок інтервалу у форматі ISO 8601"),
    ends_at: AwareDatetime = Query(None, description="Кінець інтервалу у форматі ISO 8601"),
):
    if (starts_at is None) != (ends_at is None):
        raise ApiError(400, "VALIDATION_ERROR", "Передайте обидві межі часового інтервалу")
    if starts_at is not None:
        starts_at = as_utc(starts_at)
        ends_at = as_utc(ends_at)
        if ends_at <= starts_at:
            raise ApiError(400, "VALIDATION_ERROR", "Кінець інтервалу має бути пізніше за початок")

    rooms = []
    for room in sorted(ROOMS.values(), key=lambda item: item.id):
        bookings = [
            Booking(
                game_id=game.id,
                title=game.title,
                master_id=game.master_id,
                starts_at=game.starts_at,
                ends_at=game.starts_at + timedelta(minutes=game.duration_minutes),
            )
            for game in sorted_games(list(GAMES.values()))
            if game.room_id == room.id
            and (
                starts_at is None
                or game.starts_at < ends_at
                and game.starts_at + timedelta(minutes=game.duration_minutes) > starts_at
            )
        ]
        blocks = [
            block
            for block in room_blocks(room.id)
            if starts_at is None or block.starts_at < ends_at and block.ends_at > starts_at
        ]
        rooms.append(
            CalendarRoom(
                room_id=room.id,
                name=room.name,
                capacity=room.capacity,
                is_blocked=room.is_blocked,
                bookings=bookings,
                blocks=blocks,
            )
        )
    return CalendarResponse(rooms=rooms)


@router.get(
    "/{room_id}",
    response_model=Room,
    summary="Отримати кімнату за id",
    description="Повертає одну кімнату клубу з її місткістю та статусом блокування.",
    responses=error_docs(400, 404),
)
async def get_room(
    room_id: str = Path(
        ...,
        pattern=r"^room_\d+$",
        description="Ідентифікатор кімнати",
        examples=["room_1"],
    ),
):
    return get_room_or_404(room_id)


@router.get(
    "/{room_id}/bookings",
    response_model=RoomBookingsResponse,
    summary="Отримати календар бронювань кімнати",
    description="Повертає слоти, у які кімната зайнята іграми, відсортовані за часом початку.",
    responses=error_docs(400, 404),
)
async def list_room_bookings(
    room_id: str = Path(
        ...,
        pattern=r"^room_\d+$",
        description="Ідентифікатор кімнати",
        examples=["room_1"],
    ),
):
    room = get_room_or_404(room_id)
    bookings = [
        Booking(
            game_id=g.id,
            title=g.title,
            master_id=g.master_id,
            starts_at=g.starts_at,
            ends_at=g.starts_at + timedelta(minutes=g.duration_minutes),
        )
        for g in sorted_games(list(GAMES.values()))
        if g.room_id == room_id
    ]
    return RoomBookingsResponse(
        room_id=room_id,
        is_blocked=room.is_blocked,
        bookings=bookings,
        blocks=room_blocks(room_id),
    )


@router.post(
    "/{room_id}/blocks",
    response_model=RoomBlockResponse,
    status_code=201,
    summary="Заблокувати кімнату на період",
    description=(
        "Доступно лише власнику клубу. Створює період блокування та автоматично скасовує "
        "ігри, що перетинаються з ним, зі сповіщеннями записаним гравцям."
    ),
    responses=error_docs(400, 401, 403, 404, 409),
)
async def create_room_block(
    payload: RoomBlockCreate,
    response: Response,
    user: CurrentUser,
    room_id: str = Path(..., pattern=r"^room_\d+$", description="Ідентифікатор кімнати"),
):
    require_roles(user, UserRole.owner)
    get_room_or_404(room_id)
    start = as_utc(payload.starts_at)
    end = as_utc(payload.ends_at)
    start_db = start.replace(tzinfo=None)
    end_db = end.replace(tzinfo=None)
    notifications = []

    with db_lock:
        db = store.SessionLocal()
        try:
            conflict = (
                db.query(RoomBlockModel)
                .filter(
                    RoomBlockModel.room_id == room_id,
                    RoomBlockModel.starts_at < end_db,
                    RoomBlockModel.ends_at > start_db,
                )
                .first()
            )
            if conflict:
                raise ApiError(409, "ROOM_BLOCK_CONFLICT", "Період кімнати вже заблокований")

            games = db.query(GameModel).filter(GameModel.room_id == room_id).all()
            overlapping_games = [
                game
                for game in games
                if as_utc(game.starts_at) < end
                and start < as_utc(game.starts_at) + timedelta(minutes=game.duration_minutes)
            ]
            for game in overlapping_games:
                players = [
                    Player(
                        user_id=enrollment.player_id,
                        name=enrollment.player.name,
                        enrolled_at=as_utc(enrollment.enrolled_at),
                    )
                    for enrollment in db.query(EnrollmentModel).filter(EnrollmentModel.game_id == game.id).all()
                ]
                notifications.append((game.id, game.title, players))
                db.delete(game)

            block = RoomBlockModel(room_id=room_id, starts_at=start_db, ends_at=end_db)
            db.add(block)
            db.flush()
            result = block_response(block)
            db.commit()
        finally:
            db.close()

    for game_id, title, players in notifications:
        GAMES._cache.pop(game_id, None)
        notify_game_cancelled(game_id, title, players)
    response.headers["Location"] = f"/api/v1/rooms/{room_id}/blocks/{result.id}"
    return result


@router.delete(
    "/{room_id}/blocks/{block_id}",
    status_code=204,
    summary="Скасувати блокування кімнати",
    description="Видаляє період блокування. Раніше автоматично скасовані ігри не відновлюються.",
    responses=error_docs(400, 401, 403, 404),
)
async def delete_room_block(
    user: CurrentUser,
    room_id: str = Path(..., pattern=r"^room_\d+$", description="Ідентифікатор кімнати"),
    block_id: int = Path(..., ge=1, description="Ідентифікатор блокування"),
):
    require_roles(user, UserRole.owner)
    get_room_or_404(room_id)
    with db_lock:
        db = store.SessionLocal()
        try:
            block = (
                db.query(RoomBlockModel)
                .filter(RoomBlockModel.room_id == room_id, RoomBlockModel.id == block_id)
                .first()
            )
            if block is None:
                raise ApiError(404, "ROOM_BLOCK_NOT_FOUND", "Період блокування не знайдено")
            db.delete(block)
            db.commit()
        finally:
            db.close()
    return Response(status_code=204)


@router.patch(
    "/{room_id}",
    response_model=Room,
    summary="Заблокувати або розблокувати кімнату",
    description=(
        "Доступно лише власнику клубу. Заблокувати кімнату, у якій є ігри, не можна: "
        "спочатку їх потрібно видалити (409)."
    ),
    responses=error_docs(400, 401, 403, 404, 409),
)
async def patch_room(
    payload: RoomPatch,
    user: CurrentUser,
    room_id: str = Path(
        ...,
        pattern=r"^room_\d+$",
        description="Ідентифікатор кімнати",
        examples=["room_1"],
    ),
):
    require_roles(user, UserRole.owner)
    room = get_room_or_404(room_id)
    if payload.is_blocked and any(g.room_id == room_id for g in GAMES.values()):
        raise ApiError(409, "ROOM_HAS_GAMES", "У кімнаті є заплановані ігри, спочатку видаліть їх")
    updated = room.model_copy(update={"is_blocked": payload.is_blocked})
    ROOMS[room_id] = updated
    return updated
