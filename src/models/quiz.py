import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    questions: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    quiz_type: Mapped[str] = mapped_column(String(50), nullable=False, default="multiple_choice_single", index=True)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    time_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quiz_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    quiz_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_token: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
