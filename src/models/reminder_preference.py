import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ReminderPreference(Base):
    __tablename__ = "reminder_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    email_digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    digest_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    digest_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_soon_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    overdue_cooldown_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
