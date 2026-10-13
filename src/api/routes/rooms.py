from datetime import timedelta
from typing import List

from fastapi import APIRouter, Path, Query

from errors import ApiError, error_docs
from schemas import (
    Booking,
    Pagination,
    Room,
    RoomBookingsResponse,
    RoomListResponse,
    RoomPatch,
    UserRole,
)
from security import CurrentUser, require_roles
from store import GAMES, ROOMS, sorted_games

router = APIRouter(prefix="/api/v1/rooms", tags=["Rooms"])


def get_room_or_404(room_id: str) -> Room:
    room = ROOMS.get(room_id)
    if room is None:
        raise ApiError(404, "ROOM_NOT_FOUND", f"Кімнату {room_id} не знайдено")
    return room


@router.get(
    "",
    response_model=RoomListResponse,
    summary="Отримати список кімнат",
    description="Повертає кімнати клубу з пагінацією. Кімнати відсортовані за id.",
    responses=error_docs(400),
)
async def list_rooms(
    limit: int = Query(
        20, ge=1, le=100, description="Максимальна кількість кімнат у відповіді"
    ),
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
        room_id=room_id, is_blocked=room.is_blocked, bookings=bookings
    )


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
        raise ApiError(
            409, "ROOM_HAS_GAMES", "У кімнаті є заплановані ігри, спочатку видаліть їх"
        )
    updated = room.model_copy(update={"is_blocked": payload.is_blocked})
    ROOMS[room_id] = updated
    return updated
