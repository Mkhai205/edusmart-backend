"""create flashcards tables

Revision ID: 20260322_06
Revises: 20260322_05
Create Date: 2026-03-22 23:59:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260322_06"
down_revision: str | None = "20260322_05"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flashcard_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("algorithm", sa.String(length=50), nullable=True),
        sa.Column("card_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.Column("share_token", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
    )
    op.create_index(op.f("ix_flashcard_sets_document_id"), "flashcard_sets", ["document_id"], unique=False)
    op.create_index(op.f("ix_flashcard_sets_user_id"), "flashcard_sets", ["user_id"], unique=False)
    op.create_index(op.f("ix_flashcard_sets_created_at"), "flashcard_sets", ["created_at"], unique=False)
    op.create_index(
        "ix_flashcard_sets_user_id_created_at",
        "flashcard_sets",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flashcard_sets_generation_status"),
        "flashcard_sets",
        ["generation_status"],
        unique=False,
    )

    op.create_table(
        "flashcards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_type", sa.String(length=50), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_keyword", sa.Text(), nullable=True),
        sa.Column("ease_factor", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=True),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rating", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["set_id"], ["flashcard_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flashcards_set_id"), "flashcards", ["set_id"], unique=False)
    op.create_index(op.f("ix_flashcards_card_type"), "flashcards", ["card_type"], unique=False)
    op.create_index(op.f("ix_flashcards_next_review_at"), "flashcards", ["next_review_at"], unique=False)
    op.create_index(
        "ix_flashcards_set_id_next_review_at",
        "flashcards",
        ["set_id", "next_review_at"],
        unique=False,
    )
    op.create_index(
        "ix_flashcards_next_review_at_not_null",
        "flashcards",
        ["next_review_at"],
        unique=False,
        postgresql_where=sa.text("next_review_at IS NOT NULL"),
    )

    op.alter_column("flashcard_sets", "generation_status", server_default=None)
    op.alter_column("flashcard_sets", "card_count", server_default=None)
    op.alter_column("flashcards", "repetitions", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_flashcards_next_review_at_not_null", table_name="flashcards")
    op.drop_index("ix_flashcards_set_id_next_review_at", table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_next_review_at"), table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_card_type"), table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_set_id"), table_name="flashcards")
    op.drop_table("flashcards")

    op.drop_index(op.f("ix_flashcard_sets_generation_status"), table_name="flashcard_sets")
    op.drop_index("ix_flashcard_sets_user_id_created_at", table_name="flashcard_sets")
    op.drop_index(op.f("ix_flashcard_sets_created_at"), table_name="flashcard_sets")
    op.drop_index(op.f("ix_flashcard_sets_user_id"), table_name="flashcard_sets")
    op.drop_index(op.f("ix_flashcard_sets_document_id"), table_name="flashcard_sets")
    op.drop_table("flashcard_sets")
