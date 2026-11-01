from typing import List

from fastapi import APIRouter

from errors import error_docs
from notifications import list_user_notifications
from schemas import NotificationResponse
from security import CurrentUser

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="Отримати власні сповіщення",
    description="Повертає сповіщення поточного користувача від найновішого до найстарішого.",
    responses=error_docs(401, 403),
)
async def get_notifications(user: CurrentUser):
    return [
        NotificationResponse(
            id=notification.id,
            game_id=notification.game_id,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
        for notification in list_user_notifications(user.id)
    ]
