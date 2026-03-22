"""create summaries table

Revision ID: 20260322_01
Revises: 20260321_01
Create Date: 2026-03-22 09:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260322_01"
down_revision: str | None = "20260321_01"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("share_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
    )
    op.create_index(op.f("ix_summaries_document_id"), "summaries", ["document_id"], unique=False)
    op.create_index(op.f("ix_summaries_user_id"), "summaries", ["user_id"], unique=False)
    op.create_index(op.f("ix_summaries_created_at"), "summaries", ["created_at"], unique=False)
    op.create_index(op.f("ix_summaries_share_token"), "summaries", ["share_token"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_summaries_share_token"), table_name="summaries")
    op.drop_index(op.f("ix_summaries_created_at"), table_name="summaries")
    op.drop_index(op.f("ix_summaries_user_id"), table_name="summaries")
    op.drop_index(op.f("ix_summaries_document_id"), table_name="summaries")
    op.drop_table("summaries")
