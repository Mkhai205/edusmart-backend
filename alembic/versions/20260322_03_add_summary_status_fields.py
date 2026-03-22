"""add summary status fields

Revision ID: 20260322_03
Revises: 20260322_02
Create Date: 2026-03-22 23:05:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260322_03"
down_revision: str | None = "20260322_02"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "summaries",
        sa.Column("summary_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column("summaries", sa.Column("summary_error", sa.Text(), nullable=True))
    op.add_column("summaries", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_summaries_summary_status"), "summaries", ["summary_status"], unique=False)

    op.alter_column("summaries", "summary_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_summaries_summary_status"), table_name="summaries")
    op.drop_column("summaries", "completed_at")
    op.drop_column("summaries", "summary_error")
    op.drop_column("summaries", "summary_status")
