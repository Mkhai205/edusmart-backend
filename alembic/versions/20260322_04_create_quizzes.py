"""create quizzes table

Revision ID: 20260322_04
Revises: 20260322_03
Create Date: 2026-03-22 23:45:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260322_04"
down_revision: str | None = "20260322_03"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quiz_type", sa.String(length=50), nullable=False),
        sa.Column("difficulty", sa.String(length=50), nullable=False),
        sa.Column("time_limit", sa.Integer(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quiz_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("quiz_error", sa.Text(), nullable=True),
        sa.Column("share_token", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
    )
    op.create_index(op.f("ix_quizzes_document_id"), "quizzes", ["document_id"], unique=False)
    op.create_index(op.f("ix_quizzes_user_id"), "quizzes", ["user_id"], unique=False)
    op.create_index(op.f("ix_quizzes_created_at"), "quizzes", ["created_at"], unique=False)
    op.create_index("ix_quizzes_user_id_created_at", "quizzes", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_quizzes_quiz_type"), "quizzes", ["quiz_type"], unique=False)
    op.create_index(op.f("ix_quizzes_difficulty"), "quizzes", ["difficulty"], unique=False)
    op.create_index(op.f("ix_quizzes_quiz_status"), "quizzes", ["quiz_status"], unique=False)

    op.alter_column("quizzes", "quiz_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_quizzes_quiz_status"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_difficulty"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_quiz_type"), table_name="quizzes")
    op.drop_index("ix_quizzes_user_id_created_at", table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_created_at"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_user_id"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_document_id"), table_name="quizzes")
    op.drop_table("quizzes")
