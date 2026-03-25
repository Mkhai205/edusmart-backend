import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.models.summary import Summary


class SummariesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_embedded_chunks(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_not(None))
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_embedded_chunks_by_page_range(
        self,
        *,
        document_id: uuid.UUID,
        start_page: int,
        end_page: int,
    ) -> list[DocumentChunk]:
        query = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_not(None),
                DocumentChunk.page_number >= start_page,
                DocumentChunk.page_number <= end_page,
            )
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def semantic_search_chunks(
        self,
        *,
        document_id: uuid.UUID,
        query_embedding: list[float],
        limit: int,
        min_similarity: float,
    ) -> list[tuple[DocumentChunk, float]]:
        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity_expr = (1 - distance_expr).label("similarity")

        query = (
            select(DocumentChunk, similarity_expr)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_not(None),
                similarity_expr >= min_similarity,
            )
            .order_by(distance_expr.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows]

    async def create_summary(
        self,
        *,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        mode: str,
        options: dict,
        content_markdown: str,
        share_token: str | None = None,
    ) -> Summary:
        summary = Summary(
            document_id=document_id,
            user_id=user_id,
            mode=mode,
            options=options,
            summary_status="pending",
            summary_error=None,
            content_markdown=content_markdown,
            share_token=share_token,
            completed_at=None,
        )
        self.session.add(summary)
        await self.session.flush()
        return summary

    async def get_user_summary(
        self,
        *,
        summary_id: uuid.UUID,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Summary | None:
        query = select(Summary).where(
            Summary.id == summary_id,
            Summary.document_id == document_id,
            Summary.user_id == user_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_summary_by_id(self, summary_id: uuid.UUID) -> Summary | None:
        query = select(Summary).where(Summary.id == summary_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_user_summary(self, *, document_id: uuid.UUID, user_id: uuid.UUID) -> Summary | None:
        query = (
            select(Summary)
            .where(Summary.document_id == document_id, Summary.user_id == user_id)
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_summary_status(
        self,
        *,
        summary_id: uuid.UUID,
        status_value: str,
        summary_error: str | None = None,
    ) -> None:
        summary = await self.get_summary_by_id(summary_id)
        if summary is None:
            return

        summary.summary_status = status_value
        summary.summary_error = summary_error
        if status_value == "completed":
            summary.completed_at = datetime.now(UTC)
        elif status_value in {"pending", "processing"}:
            summary.completed_at = None

        await self.session.flush()
