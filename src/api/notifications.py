"""Сповіщення гравців про скасування гри (FR-011).

Сховище в пам'яті, як і решта прототипу: сповіщення лежать у словнику за id користувача.
Фактичну відправку листа (SMTP, Notification Service у high-level-design.md) буде додано пізніше.
"""

from datetime import datetime, timezone
from typing import Dict, List

from pydantic import BaseModel

from schemas import Player


class Notification(BaseModel):
    user_id: str
    game_id: str
    message: str
    created_at: datetime


NOTIFICATIONS: Dict[str, List[Notification]] = {}


def notify_game_cancelled(game_id: str, game_title: str, players: List[Player]) -> List[Notification]:
    """Створює по одному сповіщенню для кожного записаного гравця й повертає їх."""
    created = []
    for player in players:
        notification = Notification(
            user_id=player.user_id,
            game_id=game_id,
            message=f"Гру «{game_title}» скасовано",
            created_at=datetime.now(timezone.utc),
        )
        NOTIFICATIONS.setdefault(player.user_id, []).append(notification)
        created.append(notification)
    return created
