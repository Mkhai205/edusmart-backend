"""rename summaries content_html to content_markdown

Revision ID: 20260322_02
Revises: 20260322_01
Create Date: 2026-03-22 22:40:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260322_02"
down_revision: str | None = "20260322_01"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "summaries",
        "content_html",
        new_column_name="content_markdown",
        existing_type=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "summaries",
        "content_markdown",
        new_column_name="content_html",
        existing_type=sa.Text(),
        existing_nullable=True,
    )
