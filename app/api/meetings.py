from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.crud import meeting as meeting_crud
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.booking_rule import BookingRule
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.schemas import meeting as meeting_schemas
# from app.utils.zoho_utils import send_meeting_webhook_notification
from app.utils.zoho_sync import send_zoho_notification

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/", response_model=meeting_schemas.MeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(
    meeting_in: meeting_schemas.MeetingCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if meeting_in.end_time <= meeting_in.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="end_time must be after start_time"
        )

    booking_rule = db.query(BookingRule).filter(BookingRule.id == 1).first()
    work_start = booking_rule.work_start if booking_rule else datetime.strptime("09:00", "%H:%M").time()
    work_end = booking_rule.work_end if booking_rule else datetime.strptime("18:00", "%H:%M").time()
    if meeting_in.start_time < work_start or meeting_in.end_time > work_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meetings can only be booked between {work_start:%H:%M} and {work_end:%H:%M}",
        )

    booking_rule = db.query(BookingRule).filter(BookingRule.id == 1).first()
    approval_required = booking_rule.approval_required if booking_rule else True
    if approval_required:
        meeting_in.status = "pending"

    if meeting_in.room_id is not None:
        room = db.execute(
            text("SELECT 1 FROM meeting_rooms WHERE id = :id"), 
            {"id": meeting_in.room_id}
        ).first()
        if room is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="room_id not found"
            )

        has_conflict = meeting_crud.check_room_conflict(
            db=db,
            room_id=meeting_in.room_id,
            meeting_date=meeting_in.meeting_date,
            start_time=meeting_in.start_time,
            end_time=meeting_in.end_time
        )
        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected room is already booked for this date and time range."
            )
    meeting_in.created_by = current_user.id
    user = db.execute(
        text("SELECT 1 FROM users WHERE id = :id"), 
        {"id": meeting_in.created_by}
    ).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="created_by user not found"
        )

    db_obj = meeting_crud.create_meeting(db=db, meeting_in=meeting_in)

    if db_obj.status == "pending":
        try:
            booking_rule = db.query(BookingRule).filter(BookingRule.id == 1).first()
            approver_roles = []
            if booking_rule is None or booking_rule.approver_admin:
                approver_roles.append("admin")
            if booking_rule is None or booking_rule.approver_approver:
                approver_roles.append("approver")
            recipients = db.query(User).filter(User.role.in_(approver_roles), User.is_active.is_(True)).all()
            for recipient in recipients:
                preferences = (
                    db.query(NotificationPreference)
                    .filter(NotificationPreference.user_id == recipient.id)
                    .first()
                )
                if preferences is None or preferences.inapp_enabled:
                    db.add(Notification(
                        user_id=recipient.id,
                        meeting_id=db_obj.id,
                        kind="booking_pending",
                        message=f"New booking awaiting approval: {db_obj.title}",
                    ))
            db.commit()
        except Exception:
            db.rollback()

# ZOHO-DISABLED — re-enable later
#     # Zoho Cliq Notification Trigger
#     should_invite = getattr(meeting_in, "inviteCliq", False) or getattr(meeting_in, "invite_cliq", False)
#
#     if should_invite:
#         participants = getattr(meeting_in, "participants", []) or getattr(db_obj, "participants", [])
#
#         meeting_date = getattr(db_obj, "meeting_date", "")
#         start_time_val = getattr(db_obj, "start_time", "")
#         end_time_val = getattr(db_obj, "end_time", "")
#         time_str = f"{meeting_date} {start_time_val}".strip()
#
#         background_tasks.add_task(
#             send_zoho_notification,
#             meeting_title=getattr(db_obj, "title", "Meeting"),
#             start_time=time_str or str(start_time_val),
#             end_time=str(end_time_val),
#             participants=participants,
#             meeting_room=getattr(db_obj, "room", getattr(db_obj, "meeting_room", "")),
#             meeting_id=str(getattr(db_obj, "id", ""))
#         )

    return db_obj


@router.get("/", response_model=List[meeting_schemas.MeetingOut])
def read_meetings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    date: Optional[date] = Query(None, alias="date", description="Filter meetings by date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return meeting_crud.list_meetings(
            db=db, skip=skip, limit=limit, date_filter=date
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch meetings: {str(exc)}"
        )


def _require_approver(db: Session, current_user: User) -> User:
    booking_rule = db.query(BookingRule).filter(BookingRule.id == 1).first()
    approver_admin = booking_rule.approver_admin if booking_rule else True
    approver_approver = booking_rule.approver_approver if booking_rule else True
    if not (
        (current_user.role == "admin" and approver_admin)
        or (current_user.role == "approver" and approver_approver)
    ):
        raise HTTPException(status_code=403, detail="Approver access required")
    return current_user


@router.get("/pending-approvals", response_model=List[meeting_schemas.PendingApprovalOut])
def read_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_approver(db, current_user)
    pending_meetings = (
        db.query(models.Meeting)
        .filter(models.Meeting.status == "pending")
        .order_by(models.Meeting.meeting_date, models.Meeting.start_time)
        .all()
    )
    results = []
    for meeting in pending_meetings:
        creator_name = db.query(User.name).filter(User.id == meeting.created_by).scalar() or ""
        meeting_data = meeting_schemas.MeetingOut.model_validate(meeting).model_dump()
        meeting_data["created_by_name"] = creator_name
        results.append(meeting_schemas.PendingApprovalOut.model_validate(meeting_data))
    return results


@router.post("/{meeting_id}/approve", response_model=meeting_schemas.MeetingOut)
def approve_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_approver(db, current_user)
    db_obj = meeting_crud.get_meeting(db=db, meeting_id=meeting_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if db_obj.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking is not waiting for approval")
    if db_obj.room_id is not None and meeting_crud.check_room_conflict(
        db=db,
        room_id=db_obj.room_id,
        meeting_date=db_obj.meeting_date,
        start_time=db_obj.start_time,
        end_time=db_obj.end_time,
        exclude_meeting_id=meeting_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected room is already booked for this date and time range.",
        )
    db_obj.status = "approved"
    db_obj.decided_by = current_user.id
    db_obj.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    try:
        preferences = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == db_obj.created_by)
            .first()
        )
        if preferences is None or preferences.inapp_enabled:
            db.add(Notification(
                user_id=db_obj.created_by,
                meeting_id=db_obj.id,
                kind="booking_approved",
                message=f"Your booking was approved: {db_obj.title}",
            ))
            db.commit()
    except Exception:
        db.rollback()
    return db_obj


@router.post("/{meeting_id}/reject", response_model=meeting_schemas.MeetingOut)
def reject_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_approver(db, current_user)
    db_obj = meeting_crud.get_meeting(db=db, meeting_id=meeting_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if db_obj.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking is not waiting for approval")
    db_obj.status = "rejected"
    db_obj.decided_by = current_user.id
    db_obj.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(db_obj)
    try:
        preferences = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == db_obj.created_by)
            .first()
        )
        if preferences is None or preferences.inapp_enabled:
            db.add(Notification(
                user_id=db_obj.created_by,
                meeting_id=db_obj.id,
                kind="booking_rejected",
                message=f"Your booking was rejected: {db_obj.title}",
            ))
            db.commit()
    except Exception:
        db.rollback()
    return db_obj


@router.get("/{meeting_id}", response_model=meeting_schemas.MeetingOut)
def read_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_obj = meeting_crud.get_meeting(db=db, meeting_id=meeting_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return db_obj


@router.put("/{meeting_id}", response_model=meeting_schemas.MeetingOut)
@router.patch("/{meeting_id}", response_model=meeting_schemas.MeetingOut)
def update_meeting(meeting_id: int, updates: meeting_schemas.MeetingUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_obj = meeting_crud.get_meeting(db=db, meeting_id=meeting_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    new_start = updates.start_time if updates.start_time is not None else db_obj.start_time
    new_end = updates.end_time if updates.end_time is not None else db_obj.end_time
    new_date = updates.meeting_date if updates.meeting_date is not None else db_obj.meeting_date
    target_room_id = updates.room_id if updates.room_id is not None else db_obj.room_id

    if new_end <= new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="end_time must be after start_time"
        )

    if updates.room_id is not None:
        room = db.execute(
            text("SELECT 1 FROM meeting_rooms WHERE id = :id"), 
            {"id": updates.room_id}
        ).first()
        if room is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="room_id not found"
            )

    # Room Conflict Check For Update Case
    if target_room_id is not None:
        has_conflict = meeting_crud.check_room_conflict(
            db=db,
            room_id=target_room_id,
            meeting_date=new_date,
            start_time=new_start,
            end_time=new_end,
            exclude_meeting_id=meeting_id
        )
        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected room is already booked for this date and time range."
            )

    updated = meeting_crud.update_meeting(db=db, db_obj=db_obj, updates=updates)
    return updated


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_obj = meeting_crud.get_meeting(db=db, meeting_id=meeting_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    meeting_crud.delete_meeting(db=db, db_obj=db_obj)
    return None
