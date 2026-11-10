from datetime import time

from sqlalchemy import BigInteger, Boolean, Column, Time

from app.core.database import Base


class BookingRule(Base):
    __tablename__ = "booking_rules"

    id = Column(BigInteger, primary_key=True)
    approval_required = Column(Boolean, nullable=False, default=True, server_default="true")
    work_start = Column(Time, nullable=False, default=time(9, 0), server_default="09:00")
    work_end = Column(Time, nullable=False, default=time(18, 0), server_default="18:00")
    approver_admin = Column(Boolean, nullable=False, default=True, server_default="true")
    approver_approver = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_email = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_in_app = Column(Boolean, nullable=False, default=True, server_default="true")
