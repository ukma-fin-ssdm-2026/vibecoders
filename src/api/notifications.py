"""Сповіщення гравців про скасування гри (FR-011).

Сховище в пам'яті, як і решта прототипу: сповіщення лежать у словнику за id користувача.
Фактичну відправку листа (SMTP, Notification Service у high-level-design.md) буде додано пізніше.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel

from schemas import Player


class Notification(BaseModel):
    user_id: str
    game_id: Optional[str] = None
    message: str
    created_at: datetime
    id: Optional[int] = None
    is_read: bool = False


NOTIFICATIONS: Dict[str, List[Notification]] = {}


def list_user_notifications(user_id: str) -> List[Notification]:
    """Повертає сповіщення одного користувача від найновішого до найстарішого."""
    return sorted(NOTIFICATIONS.get(user_id, []), key=lambda notification: notification.created_at, reverse=True)


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
