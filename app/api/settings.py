import re
from datetime import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.booking_rule import BookingRule
from app.schemas.booking_rule import BookingRulesOut, BookingRulesUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULTS = {
    "approval_required": True,
    "work_start": "09:00",
    "work_end": "18:00",
    "approver_admin": True,
    "approver_approver": True,
    "notify_email": True,
    "notify_in_app": True,
}


def _format_rules(rule: BookingRule) -> BookingRulesOut:
    return BookingRulesOut(
        approval_required=rule.approval_required,
        work_start=rule.work_start.strftime("%H:%M"),
        work_end=rule.work_end.strftime("%H:%M"),
        approver_admin=rule.approver_admin,
        approver_approver=rule.approver_approver,
        notify_email=rule.notify_email,
        notify_in_app=rule.notify_in_app,
    )


@router.get("/booking-rules", response_model=BookingRulesOut)
def get_booking_rules(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rule = db.query(BookingRule).filter(BookingRule.id == 1).first()
    if rule is None:
        return BookingRulesOut(**DEFAULTS)
    return _format_rules(rule)


@router.put("/booking-rules", response_model=BookingRulesOut)
def update_booking_rules(
    updates: BookingRulesUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", updates.work_start) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", updates.work_end
    ):
        raise HTTPException(status_code=400, detail="work_start and work_end must be HH:MM")

    work_start = time.fromisoformat(updates.work_start)
    work_end = time.fromisoformat(updates.work_end)
    if work_end <= work_start:
        raise HTTPException(status_code=400, detail="work_end must be after work_start")
    if not updates.approver_admin and not updates.approver_approver:
        raise HTTPException(status_code=400, detail="At least one approver role must be selected")

    rule = db.query(BookingRule).filter(BookingRule.id == 1).first()
    if rule is None:
        rule = BookingRule(id=1)
        db.add(rule)

    rule.approval_required = updates.approval_required
    rule.work_start = work_start
    rule.work_end = work_end
    rule.approver_admin = updates.approver_admin
    rule.approver_approver = updates.approver_approver
    rule.notify_email = updates.notify_email
    rule.notify_in_app = updates.notify_in_app
    db.commit()
    db.refresh(rule)
    return _format_rules(rule)
