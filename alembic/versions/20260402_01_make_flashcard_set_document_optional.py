"""make flashcard set document optional

Revision ID: 20260402_01
Revises: 20260323_01
Create Date: 2026-04-02 17:10:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260402_01"
down_revision: str | None = "20260323_01"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "flashcard_sets",
        "document_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM flashcard_sets WHERE document_id IS NULL"))
    op.alter_column(
        "flashcard_sets",
        "document_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
