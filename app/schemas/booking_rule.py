from pydantic import BaseModel


class BookingRulesOut(BaseModel):
    approval_required: bool
    work_start: str
    work_end: str
    approver_admin: bool
    approver_approver: bool
    notify_email: bool
    notify_in_app: bool


class BookingRulesUpdate(BaseModel):
    approval_required: bool
    work_start: str
    work_end: str
    approver_admin: bool
    approver_approver: bool
    notify_email: bool
    notify_in_app: bool


class NotificationPreferencesOut(BaseModel):
    email_enabled: bool
    inapp_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    email_enabled: bool
    inapp_enabled: bool
