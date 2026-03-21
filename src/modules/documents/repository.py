import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_chunk import DocumentChunk


class DocumentsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        file_url: str,
        object_key: str,
        content_type: str,
        file_size: int,
        total_pages: int | None,
        is_public: bool,
        extraction_status: str,
    ) -> Document:
        document = Document(
            user_id=user_id,
            title=title,
            file_url=file_url,
            object_key=object_key,
            content_type=content_type,
            file_size=file_size,
            total_pages=total_pages,
            is_public=is_public,
            extraction_status=extraction_status,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_user_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_extraction_status(
        self,
        document_id: uuid.UUID,
        *,
        status_value: str,
        extraction_error: str | None = None,
        extracted_at: datetime | None = None,
    ) -> None:
        query = (
            update(Document)
            .where(Document.id == document_id)
            .values(
                extraction_status=status_value,
                extraction_error=extraction_error,
                extracted_at=extracted_at,
            )
        )
        await self.session.execute(query)

    async def mark_extraction_completed(self, document_id: uuid.UUID, total_pages: int) -> None:
        now = datetime.now(UTC)
        query = (
            update(Document)
            .where(Document.id == document_id)
            .values(
                extraction_status="completed",
                extraction_error=None,
                extracted_at=now,
                total_pages=total_pages,
            )
        )
        await self.session.execute(query)

    async def delete_chunks_by_document(self, document_id: uuid.UUID) -> None:
        query = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        await self.session.execute(query)

    async def bulk_create_chunks(self, document_id: uuid.UUID, chunks: list[dict]) -> None:
        records = [
            DocumentChunk(
                document_id=document_id,
                page_number=chunk["page_number"],
                chunk_index=chunk["chunk_index"],
                text_content=chunk["text_content"],
                bbox=chunk.get("bbox"),
                element_type=chunk["element_type"],
            )
            for chunk in chunks
        ]
        self.session.add_all(records)

    async def get_unembedded_chunks(self, document_id: uuid.UUID, *, limit: int) -> list[DocumentChunk]:
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_(None))
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def bulk_update_embeddings(self, embeddings_by_chunk_id: dict[uuid.UUID, list[float]]) -> int:
        for chunk_id, embedding in embeddings_by_chunk_id.items():
            query = update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(embedding=embedding)
            await self.session.execute(query)

        return len(embeddings_by_chunk_id)
