"""create quiz attempts table

Revision ID: 20260322_05
Revises: 20260322_04
Create Date: 2026-03-22 23:58:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260322_05"
down_revision: str | None = "20260322_04"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("time_spent", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quiz_attempts_quiz_id"), "quiz_attempts", ["quiz_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_user_id"), "quiz_attempts", ["user_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_score"), "quiz_attempts", ["score"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_completed_at"), "quiz_attempts", ["completed_at"], unique=False)
    op.create_index("ix_quiz_attempts_quiz_id_completed_at", "quiz_attempts", ["quiz_id", "completed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_quiz_id_completed_at", table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_completed_at"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_score"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_user_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_quiz_id"), table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
