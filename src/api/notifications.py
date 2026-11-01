"""Сповіщення гравців про скасування гри (FR-011).

Сповіщення зберігаються в таблиці ``notifications`` (див. models.Notification), тому не зникають
після перезапуску сервера. Фактичну відправку листа (SMTP, Notification Service у high-level-design.md)
буде додано пізніше.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel

import db
from models import Notification as NotificationModel
from schemas import Player


class Notification(BaseModel):
    user_id: str
    game_id: Optional[str] = None
    message: str
    created_at: datetime
    id: Optional[int] = None
    is_read: bool = False


def _to_schema(row: NotificationModel) -> Notification:
    return Notification(
        id=row.id,
        user_id=row.user_id,
        game_id=row.game_id,
        message=row.message,
        created_at=row.created_at.replace(tzinfo=timezone.utc),
        is_read=bool(row.is_read),
    )


def list_user_notifications(user_id: str) -> List[Notification]:
    """Повертає сповіщення одного користувача від найновішого до найстарішого."""
    return sorted(NOTIFICATIONS.get(user_id, []), key=lambda notification: notification.created_at, reverse=True)


def notify_game_cancelled(game_id: str, game_title: str, players: List[Player]) -> List[Notification]:
    """Створює по одному сповіщенню для кожного записаного гравця (в одній транзакції) і повертає їх."""
    if not players:
        return []
    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    with db.session_scope() as session:
        rows = [
            NotificationModel(
                user_id=player.user_id,
                game_id=game_id,
                message=f"Гру «{game_title}» скасовано",
                created_at=created_at,
                is_read=False,
            )
            for player in players
        ]
        session.add_all(rows)
        session.flush()
        return [_to_schema(row) for row in rows]


def list_user_notifications(
    user_id: Optional[str] = None,
    unread_only: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Notification]:
    """Сповіщення користувача (або всі, якщо user_id не задано): спершу найновіші."""
    with db.session_scope() as session:
        query = session.query(NotificationModel)
        if user_id is not None:
            query = query.filter(NotificationModel.user_id == user_id)
        if unread_only:
            query = query.filter(NotificationModel.is_read.is_(False))
        query = query.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc()).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return [_to_schema(row) for row in query.all()]


def mark_notification_read(user_id: str, notification_id: int) -> Optional[Notification]:
    """Позначає сповіщення прочитаним. None, якщо його немає або воно належить іншому користувачу."""
    with db.session_scope() as session:
        row = (
            session.query(NotificationModel)
            .filter(NotificationModel.id == notification_id, NotificationModel.user_id == user_id)
            .first()
        )
        if row is None:
            return None
        row.is_read = True
        session.flush()
        return _to_schema(row)
