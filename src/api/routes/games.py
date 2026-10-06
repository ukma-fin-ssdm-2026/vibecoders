from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field
from typing import List, Optional

router = APIRouter(prefix="/api/v1/games", tags=["Games"])

class GameBase(BaseModel):
    title: str = Field(..., min_length=3, description="Назва гри")
    system: str = Field(..., description="Ігрова система")
    max_players: int = Field(..., ge=2, le=8, description="Максимальна кількість гравців")

class GameResponse(GameBase):
    id: str
    current_players: int = 0

mock_db = {}

@router.get("", response_model=List[GameResponse], summary="Отримати список ігор")
async def list_games():
    return list(mock_db.values())

@router.post("", response_model=GameResponse, status_code=status.HTTP_201_CREATED, summary="Створити гру")
async def create_game(game: GameBase):
    game_id = f"game_{len(mock_db) + 1}"
    new_game = GameResponse(id=game_id, **game.dict())
    mock_db[game_id] = new_game
    return new_game

@router.get("/{game_id}", response_model=GameResponse, summary="Отримати деталі гри")
async def get_game(game_id: str = Path(...)):
    if game_id not in mock_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Гру не знайдено")
    return mock_db[game_id]

@router.put("/{game_id}", response_model=GameResponse, summary="Оновити гру повністю")
async def update_game(game_id: str, game: GameBase):
    if game_id not in mock_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Гру не знайдено")
    updated_game = GameResponse(id=game_id, **game.dict())
    mock_db[game_id] = updated_game
    return updated_game

@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Скасувати гру")
async def delete_game(game_id: str):
    if game_id not in mock_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Гру не знайдено")
    del mock_db[game_id]
