"""add document extraction status and chunks table

Revision ID: 20260320_02
Revises: 20260320_01
Create Date: 2026-03-20 00:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260320_02"
down_revision: str | None = "20260320_01"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
    )
    op.add_column("documents", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("element_type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_page_number"), "document_chunks", ["page_number"], unique=False)
    op.create_index(
        "ix_document_chunks_document_id_chunk_index",
        "document_chunks",
        ["document_id", "chunk_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id_chunk_index", table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_page_number"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_column("documents", "extracted_at")
    op.drop_column("documents", "extraction_error")
    op.drop_column("documents", "extraction_status")
