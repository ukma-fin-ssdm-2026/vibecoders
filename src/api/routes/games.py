from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Path, Query, Response

from errors import ApiError, error_docs
from schemas import (
    Game,
    GameBase,
    GameCreate,
    GameListResponse,
    GamePatch,
    GameUpdate,
    Pagination,
    Player,
    PlayersResponse,
    UserRole,
)
from security import CurrentUser, require_roles
from store import (
    ENROLLMENTS,
    GAMES,
    ROOMS,
    USERS,
    GameRecord,
    find_busy_game,
    next_game_id,
    sorted_games,
    to_game,
)

router = APIRouter(prefix="/api/v1/games", tags=["Games"])

GameId = Path(
    ..., pattern=r"^game_\d+$", description="Ідентифікатор гри", examples=["game_1"]
)


def get_game_or_404(game_id: str) -> GameRecord:
    record = GAMES.get(game_id)
    if record is None:
        raise ApiError(404, "GAME_NOT_FOUND", f"Гру {game_id} не знайдено")
    return record


def ensure_can_manage(record: GameRecord, user_id: str, role: UserRole) -> None:
    if role != UserRole.owner and record.master_id != user_id:
        raise ApiError(
            403, "FORBIDDEN", "Керувати грою може лише її майстер або власник клубу"
        )


def ensure_schedule_is_valid(
    data: GameBase, master_id: str, exclude_game_id: Optional[str] = None
) -> None:
    room = ROOMS.get(data.room_id)
    if room is None:
        raise ApiError(404, "ROOM_NOT_FOUND", f"Кімнату {data.room_id} не знайдено")
    if room.is_blocked:
        raise ApiError(409, "ROOM_BLOCKED", "Кімната заблокована власником клубу")
    if data.max_players > room.capacity:
        raise ApiError(
            409,
            "ROOM_CAPACITY_EXCEEDED",
            f"Місткість кімнати {room.id}: {room.capacity} місць",
        )
    room_conflict = find_busy_game(
        data.starts_at,
        data.duration_minutes,
        room_id=data.room_id,
        exclude_game_id=exclude_game_id,
    )
    if room_conflict:
        raise ApiError(
            409, "ROOM_BUSY", f"Кімната зайнята на цей час грою {room_conflict.id}"
        )
    master_conflict = find_busy_game(
        data.starts_at,
        data.duration_minutes,
        master_id=master_id,
        exclude_game_id=exclude_game_id,
    )
    if master_conflict:
        raise ApiError(
            409, "MASTER_BUSY", f"Майстер уже веде гру {master_conflict.id} у цей час"
        )
    if exclude_game_id and data.max_players < len(ENROLLMENTS.get(exclude_game_id, [])):
        raise ApiError(
            409,
            "MAX_PLAYERS_BELOW_ENROLLED",
            "Нове обмеження менше за кількість уже записаних гравців",
        )


@router.get(
    "",
    response_model=GameListResponse,
    summary="Отримати список ігор",
    description="Повертає ігри з пагінацією та фільтрами. Порядок гарантований: за часом початку, потім за id.",
    responses=error_docs(400),
)
async def list_games(
    limit: int = Query(
        20, ge=1, le=100, description="Максимальна кількість ігор у відповіді"
    ),
    offset: int = Query(0, ge=0, description="Скільки ігор пропустити"),
    room_id: Optional[str] = Query(
        None, pattern=r"^room_\d+$", description="Показати лише ігри в цій кімнаті"
    ),
    master_id: Optional[str] = Query(
        None, pattern=r"^user_\d+$", description="Показати лише ігри цього майстра"
    ),
):
    records = sorted_games(list(GAMES.values()))
    if room_id:
        records = [r for r in records if r.room_id == room_id]
    if master_id:
        records = [r for r in records if r.master_id == master_id]
    page = records[offset : offset + limit]
    return GameListResponse(
        items=[to_game(r) for r in page],
        pagination=Pagination(
            limit=limit,
            offset=offset,
            total=len(records),
            has_more=offset + limit < len(records),
        ),
    )


@router.post(
    "",
    response_model=Game,
    status_code=201,
    summary="Створити гру",
    description="Створює гру. Майстром стає автор запиту. Доступно ролям master та owner.",
    responses=error_docs(400, 401, 403, 404, 409),
)
async def create_game(payload: GameCreate, response: Response, user: CurrentUser):
    require_roles(user, UserRole.master, UserRole.owner)
    ensure_schedule_is_valid(payload, master_id=user.id)
    record = GameRecord(id=next_game_id(), master_id=user.id, **payload.model_dump())
    GAMES[record.id] = record
    ENROLLMENTS[record.id] = []
    response.headers["Location"] = f"/api/v1/games/{record.id}"
    return to_game(record)


@router.get(
    "/{game_id}",
    response_model=Game,
    summary="Отримати гру за id",
    description="Повертає деталі однієї гри разом із кількістю записаних гравців.",
    responses=error_docs(400, 404),
)
async def get_game(game_id: str = GameId):
    return to_game(get_game_or_404(game_id))


@router.put(
    "/{game_id}",
    response_model=Game,
    summary="Повністю замінити гру",
    description="Замінює всі поля гри. Усі поля тіла обов'язкові. Повторний запит з тим самим тілом дає той самий результат.",
    responses=error_docs(400, 401, 403, 404, 409),
)
async def replace_game(payload: GameUpdate, user: CurrentUser, game_id: str = GameId):
    record = get_game_or_404(game_id)
    ensure_can_manage(record, user.id, user.role)
    ensure_schedule_is_valid(
        payload, master_id=record.master_id, exclude_game_id=game_id
    )
    updated = GameRecord(id=game_id, master_id=record.master_id, **payload.model_dump())
    GAMES[game_id] = updated
    return to_game(updated)


@router.patch(
    "/{game_id}",
    response_model=Game,
    summary="Частково оновити гру",
    description="Змінює лише передані поля. Порожнє тіло запиту — помилка валідації.",
    responses=error_docs(400, 401, 403, 404, 409),
)
async def patch_game(payload: GamePatch, user: CurrentUser, game_id: str = GameId):
    record = get_game_or_404(game_id)
    ensure_can_manage(record, user.id, user.role)
    changes = {
        key: value for key, value in payload.model_dump().items() if value is not None
    }
    if not changes:
        raise ApiError(
            400, "VALIDATION_ERROR", "Передайте хоча б одне поле для оновлення"
        )
    base_fields = {key: getattr(record, key) for key in GameBase.model_fields}
    merged = GameBase(**{**base_fields, **changes})
    ensure_schedule_is_valid(
        merged, master_id=record.master_id, exclude_game_id=game_id
    )
    updated = GameRecord(id=game_id, master_id=record.master_id, **merged.model_dump())
    GAMES[game_id] = updated
    return to_game(updated)


@router.delete(
    "/{game_id}",
    status_code=204,
    summary="Видалити гру",
    description="Видаляє гру разом із записами гравців і звільняє кімнату. Доступно майстру гри та власнику клубу.",
    responses=error_docs(400, 401, 403, 404),
)
async def delete_game(user: CurrentUser, game_id: str = GameId):
    record = get_game_or_404(game_id)
    ensure_can_manage(record, user.id, user.role)
    del GAMES[game_id]
    ENROLLMENTS.pop(game_id, None)
    return Response(status_code=204)


@router.get(
    "/{game_id}/players",
    response_model=PlayersResponse,
    summary="Отримати список гравців гри",
    description="Повертає записаних гравців та лічильник заповненості. Потрібна автентифікація.",
    responses=error_docs(400, 401, 404),
)
async def list_players(user: CurrentUser, game_id: str = GameId):
    record = get_game_or_404(game_id)
    players = ENROLLMENTS.get(game_id, [])
    return PlayersResponse(
        game_id=game_id,
        current_players=len(players),
        max_players=record.max_players,
        players=players,
    )


@router.post(
    "/{game_id}/players",
    response_model=Player,
    status_code=201,
    summary="Записатися на гру",
    description="Записує автора запиту на гру. Тіло запиту не потрібне. Помилка 409, якщо місць немає або гравець уже записаний.",
    responses=error_docs(400, 401, 404, 409),
)
async def enroll_player(response: Response, user: CurrentUser, game_id: str = GameId):
    record = get_game_or_404(game_id)
    players = ENROLLMENTS.setdefault(game_id, [])
    if any(p.user_id == user.id for p in players):
        raise ApiError(409, "ALREADY_ENROLLED", "Ви вже записані на цю гру")
    if len(players) >= record.max_players:
        raise ApiError(409, "GAME_FULL", "Вільних місць немає")
    player = Player(
        user_id=user.id, name=user.name, enrolled_at=datetime.now(timezone.utc)
    )
    players.append(player)
    response.headers["Location"] = f"/api/v1/games/{game_id}/players/{user.id}"
    return player


@router.delete(
    "/{game_id}/players/{user_id}",
    status_code=204,
    summary="Скасувати запис гравця",
    description="Скасовує запис гравця. Доступно самому гравцеві, майстру гри та власнику клубу.",
    responses=error_docs(400, 401, 403, 404),
)
async def remove_player(
    user: CurrentUser,
    game_id: str = GameId,
    user_id: str = Path(
        ...,
        pattern=r"^user_\d+$",
        description="Ідентифікатор гравця",
        examples=["user_2"],
    ),
):
    record = get_game_or_404(game_id)
    is_self = user.id == user_id
    is_manager = user.role == UserRole.owner or record.master_id == user.id
    if not (is_self or is_manager):
        raise ApiError(
            403,
            "FORBIDDEN",
            "Скасувати запис може сам гравець, майстер гри або власник клубу",
        )
    players = ENROLLMENTS.get(game_id, [])
    remaining = [p for p in players if p.user_id != user_id]
    if len(remaining) == len(players):
        raise ApiError(
            404,
            "ENROLLMENT_NOT_FOUND",
            f"Гравець {user_id} не записаний на гру {game_id}",
        )
    ENROLLMENTS[game_id] = remaining
    return Response(status_code=204)
