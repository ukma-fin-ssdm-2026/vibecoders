from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class UserRole(str, Enum):
    player = "player"
    master = "master"
    owner = "owner"


class User(BaseModel):
    id: str
    name: str
    role: UserRole


class ErrorDetail(BaseModel):
    field: str = Field(..., description="Шлях до проблемного поля", examples=["body.max_players"])
    message: str = Field(
        ...,
        description="Що саме не так з полем",
        examples=["Input should be less than or equal to 8"],
    )


class ErrorBody(BaseModel):
    code: str = Field(..., description="Машинозчитуваний код помилки", examples=["VALIDATION_ERROR"])
    message: str = Field(
        ...,
        description="Опис помилки для людини",
        examples=["Вхідні дані не пройшли валідацію"],
    )
    details: List[ErrorDetail] = Field(default_factory=list, description="Деталі по окремих полях")


class ErrorResponse(BaseModel):
    error: ErrorBody


class Pagination(BaseModel):
    limit: int = Field(..., ge=1, le=100, description="Кількість елементів на сторінці", examples=[20])
    offset: int = Field(..., ge=0, description="Скільки елементів пропущено", examples=[0])
    total: int = Field(..., ge=0, description="Загальна кількість елементів за фільтром", examples=[2])
    has_more: bool = Field(..., description="Чи є наступна сторінка", examples=[False])


class GameBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Назва гри",
        examples=["Прокляття Страда"],
    )
    system: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Ігрова система",
        examples=["D&D 5e"],
    )
    room_id: str = Field(
        ...,
        pattern=r"^room_\d+$",
        description="Ідентифікатор кімнати",
        examples=["room_1"],
    )
    starts_at: AwareDatetime = Field(
        ...,
        description="Початок гри (ISO 8601 з часовим поясом)",
        examples=["2026-10-10T18:00:00Z"],
    )
    duration_minutes: int = Field(..., ge=30, le=720, description="Тривалість гри в хвилинах", examples=[180])
    max_players: int = Field(..., ge=2, le=8, description="Максимальна кількість гравців", examples=[5])


class GameCreate(GameBase):
    pass


class GameUpdate(GameBase):
    pass


class GamePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, min_length=3, max_length=100, description="Нова назва гри")
    system: Optional[str] = Field(None, min_length=2, max_length=50, description="Нова ігрова система")
    room_id: Optional[str] = Field(None, pattern=r"^room_\d+$", description="Нова кімната")
    starts_at: Optional[AwareDatetime] = Field(None, description="Новий час початку")
    duration_minutes: Optional[int] = Field(None, ge=30, le=720, description="Нова тривалість у хвилинах")
    max_players: Optional[int] = Field(None, ge=2, le=8, description="Нова максимальна кількість гравців")


class Game(GameBase):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "game_1",
                    "title": "Прокляття Страда",
                    "system": "D&D 5e",
                    "room_id": "room_1",
                    "starts_at": "2026-10-10T18:00:00Z",
                    "duration_minutes": 180,
                    "max_players": 5,
                    "master_id": "user_1",
                    "current_players": 1,
                }
            ]
        }
    )

    id: str = Field(..., description="Ідентифікатор гри", examples=["game_1"])
    master_id: str = Field(..., description="Ідентифікатор майстра, який веде гру", examples=["user_1"])
    current_players: int = Field(..., ge=0, description="Скільки гравців уже записано", examples=[1])


class GameListResponse(BaseModel):
    items: List[Game] = Field(..., description="Ігри, відсортовані за часом початку, потім за id")
    pagination: Pagination


class Player(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "user_2",
                    "name": "Марія",
                    "enrolled_at": "2026-10-01T09:30:00Z",
                }
            ]
        }
    )

    user_id: str = Field(..., description="Ідентифікатор гравця", examples=["user_2"])
    name: str = Field(..., description="Ім'я або нікнейм гравця", examples=["Марія"])
    enrolled_at: datetime = Field(..., description="Коли гравець записався")


class PlayersResponse(BaseModel):
    game_id: str = Field(..., examples=["game_1"])
    current_players: int = Field(..., ge=0, description="Скільки місць зайнято", examples=[1])
    max_players: int = Field(..., ge=2, description="Скільки місць усього", examples=[5])
    players: List[Player] = Field(..., description="Записані гравці")


class Room(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "room_1",
                    "name": "Зала «Дракон»",
                    "capacity": 8,
                    "is_blocked": False,
                }
            ]
        }
    )

    id: str = Field(..., description="Ідентифікатор кімнати", examples=["room_1"])
    name: str = Field(..., description="Назва кімнати", examples=["Зала «Дракон»"])
    capacity: int = Field(
        ..., ge=1, description="Максимальна місткість кімнати", examples=[8]
    )
    is_blocked: bool = Field(
        ..., description="Чи заблокована кімната власником клубу", examples=[False]
    )
    current_players: int = Field(
        0, description="Поточна кількість гравців", examples=[2]
    )

    @model_validator(mode="after")
    def check_players_not_exceed_capacity(self) -> "Room":
        if self.current_players > self.capacity:
            raise ValueError(
                "Поточна кількість гравців не може перевищувати місткість кімнати"
            )
        return self

    def is_full(self) -> bool:
        return self.current_players >= self.capacity


class RoomListResponse(BaseModel):
    items: List[Room]
    pagination: Pagination


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        ...,
        min_length=5,
        max_length=100,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Електронна пошта",
        examples=["master@club.test"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Пароль",
        examples=["master-pass-1"],
    )


class TokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description=("Токен для заголовка Authorization: Bearer"),
        examples=["master-token"],
    )
    token_type: str = Field("bearer", description="Тип токена", examples=["bearer"])
    role: UserRole = Field(..., description="Роль користувача")


class RoomPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_blocked: bool = Field(..., description="Заблокувати (true) або розблокувати (false) кімнату")


class Booking(BaseModel):
    game_id: str = Field(..., examples=["game_1"])
    title: str = Field(..., examples=["Прокляття Страда"])
    master_id: str = Field(..., examples=["user_1"])
    starts_at: AwareDatetime = Field(..., examples=["2026-10-10T18:00:00Z"])
    ends_at: AwareDatetime = Field(..., examples=["2026-10-10T21:00:00Z"])


class RoomBookingsResponse(BaseModel):
    room_id: str = Field(..., examples=["room_1"])
    is_blocked: bool = Field(..., examples=[False])
    bookings: List[Booking] = Field(
        ...,
        description=("Заброньовані слоти, відсортовані за часом початку"),
    )
