"""add embedding vector column to document_chunks

Revision ID: 20260321_01
Revises: 20260320_02
Create Date: 2026-03-21 09:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "20260321_01"
down_revision: str | None = "20260320_02"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("document_chunks", sa.Column("embedding", Vector(768), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding")
