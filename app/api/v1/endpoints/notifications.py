from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationItem(BaseModel):
    id: int
    kind: str
    message: str
    meeting_id: int | None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationsResponse(BaseModel):
    items: List[NotificationItem]
    unread_count: int


class MarkReadResponse(BaseModel):
    unread_count: int


@router.get("", response_model=NotificationsResponse)
def read_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(50)
        .all()
    )
    unread_count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
    )
    return NotificationsResponse(items=notifications, unread_count=unread_count)


@router.post("/mark-read", response_model=MarkReadResponse)
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    ).update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return MarkReadResponse(unread_count=0)
