from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_id = Column(BigInteger, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
