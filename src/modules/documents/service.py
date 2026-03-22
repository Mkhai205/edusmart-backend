import re
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.storage.minio_client import MinioStorageClient
from src.models.user import User
from src.modules.documents.extraction_service import DocumentExtractionService
from src.modules.documents.repository import DocumentsRepository
from src.modules.documents.vectorization_service import DocumentVectorizationService
from src.modules.documents.schemas import (
    DocumentDownloadResponse,
    DocumentDetailResponse,
    DocumentExtractionStatusResponse,
    DocumentListItemResponse,
    SemanticSearchChunkResult,
    SemanticSearchResponse,
    DocumentUploadResponse,
)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}
logger = logging.getLogger("uvicorn.error")


class DocumentsService:
    def __init__(self, session: AsyncSession, minio_client: MinioStorageClient):
        self.session = session
        self.repo = DocumentsRepository(session)
        self.minio_client = minio_client

    async def upload_document(self, *, current_user: User, filename: str, content_type: str, content: bytes) -> DocumentUploadResponse:
        filename = filename or "document.pdf"
        content_type = content_type or ""

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF files are allowed")

        file_size = len(content)

        if file_size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File size exceeds 20MB")

        object_key = self._build_object_key(current_user.id, filename)
        uploaded = False

        try:
            await self.minio_client.upload_bytes(object_key=object_key, content=content, content_type=content_type)
            uploaded = True
            file_url = self.minio_client.build_file_url(object_key)

            document = await self.repo.create_document(
                user_id=current_user.id,
                title=self._build_title(filename),
                file_url=file_url,
                object_key=object_key,
                content_type=content_type,
                file_size=file_size,
                total_pages=None,
                is_public=False,
                extraction_status="pending",
            )
            await self.session.commit()

            download_url = await self.minio_client.generate_download_url(object_key=object_key)
            return DocumentUploadResponse(
                document_id=document.id,
                title=document.title,
                file_url=document.file_url,
                object_key=document.object_key,
                content_type=document.content_type,
                file_size=document.file_size,
                total_pages=document.total_pages,
                is_public=document.is_public,
                extraction_status=document.extraction_status,
                created_at=document.created_at,
                download_url=download_url,
            )
        except HTTPException:
            await self.session.rollback()
            if uploaded:
                await self.minio_client.delete_object(object_key)
            raise
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            if uploaded:
                await self.minio_client.delete_object(object_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload document",
            ) from exc

    async def generate_download_link(
        self,
        *,
        document_id: uuid.UUID,
        current_user: User,
        expires_in_seconds: int = 900,
    ) -> DocumentDownloadResponse:
        document = await self.repo.get_user_document(document_id=document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        download_url = await self.minio_client.generate_download_url(
            object_key=document.object_key,
            expires_seconds=expires_in_seconds,
        )

        return DocumentDownloadResponse(
            document_id=document.id,
            download_url=download_url,
            expires_in_seconds=expires_in_seconds,
        )

    async def list_documents(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
    ) -> list[DocumentListItemResponse]:
        documents = await self.repo.list_user_documents(current_user.id, limit=limit, offset=offset)
        return [
            DocumentListItemResponse(
                document_id=document.id,
                title=document.title,
                content_type=document.content_type,
                file_size=document.file_size,
                total_pages=document.total_pages,
                extraction_status=document.extraction_status,
                created_at=document.created_at,
            )
            for document in documents
        ]

    async def get_document_detail(
        self,
        *,
        document_id: uuid.UUID,
        current_user: User,
    ) -> DocumentDetailResponse:
        document = await self.repo.get_user_document(document_id=document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        download_url = await self.minio_client.generate_download_url(object_key=document.object_key)
        return DocumentDetailResponse(
            document_id=document.id,
            title=document.title,
            file_url=document.file_url,
            object_key=document.object_key,
            content_type=document.content_type,
            file_size=document.file_size,
            total_pages=document.total_pages,
            is_public=document.is_public,
            extraction_status=document.extraction_status,
            extraction_error=document.extraction_error,
            extracted_at=document.extracted_at,
            created_at=document.created_at,
            download_url=download_url,
        )

    async def get_document_extraction_status(
        self,
        *,
        document_id: uuid.UUID,
        current_user: User,
    ) -> DocumentExtractionStatusResponse:
        document = await self.repo.get_user_document(document_id=document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        return DocumentExtractionStatusResponse(
            document_id=document.id,
            extraction_status=document.extraction_status,
            total_pages=document.total_pages,
            extraction_error=document.extraction_error,
            extracted_at=document.extracted_at,
        )

    async def queue_vectorization_retry(
        self,
        *,
        document_id: uuid.UUID,
        current_user: User,
    ) -> DocumentExtractionStatusResponse:
        document = await self.repo.get_user_document(document_id=document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        await self.repo.update_extraction_status(
            document_id,
            status_value="processing",
            extraction_error=None,
            extracted_at=document.extracted_at,
        )
        await self.session.commit()

        return DocumentExtractionStatusResponse(
            document_id=document.id,
            extraction_status="processing",
            total_pages=document.total_pages,
            extraction_error=None,
            extracted_at=document.extracted_at,
        )

    async def semantic_search(
        self,
        *,
        document_id: uuid.UUID,
        query: str,
        limit: int,
        min_similarity: float,
        current_user: User,
    ) -> SemanticSearchResponse:
        document = await self.repo.get_user_document(document_id=document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        settings = get_settings()
        vectorization_service = DocumentVectorizationService(settings)
        query_embedding = await vectorization_service.embed_query(query)

        rows = await self.repo.semantic_search_chunks(
            document_id=document_id,
            query_embedding=query_embedding,
            limit=limit,
            min_similarity=min_similarity,
        )
        results = [
            SemanticSearchChunkResult(
                chunk_id=chunk.id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text_content=chunk.text_content,
                bbox=chunk.bbox,
                element_type=chunk.element_type,
                similarity=similarity,
            )
            for chunk, similarity in rows
        ]
        return SemanticSearchResponse(document_id=document_id, query=query, results=results)

    @staticmethod
    async def run_extraction_pipeline(
        document_id: uuid.UUID,
        object_key: str,
        minio_client: MinioStorageClient,
    ) -> None:
        settings = get_settings()
        extraction_service = DocumentExtractionService(minio_client)
        vectorization_service = DocumentVectorizationService(settings)
        async with AsyncSessionFactory() as session:
            repo = DocumentsRepository(session)

            await repo.update_extraction_status(document_id, status_value="processing", extraction_error=None)
            await session.commit()

            try:
                total_pages, chunks = await extraction_service.extract_from_object(object_key)

                await repo.delete_chunks_by_document(document_id)
                if chunks:
                    await repo.bulk_create_chunks(document_id, chunks)
                    await session.flush()
                    embedded_count = await DocumentsService._vectorize_document_chunks(
                        repo=repo,
                        vectorization_service=vectorization_service,
                        document_id=document_id,
                        batch_size=settings.embedding_batch_size,
                    )
                    logger.info("Document %s vectorized chunks: %s", document_id, embedded_count)
                await repo.mark_extraction_completed(document_id, total_pages)
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                await repo.update_extraction_status(
                    document_id,
                    status_value="failed",
                    extraction_error=str(exc)[:1000],
                    extracted_at=datetime.now(UTC),
                )
                await session.commit()

    @staticmethod
    async def run_vectorization_pipeline(document_id: uuid.UUID) -> None:
        settings = get_settings()
        vectorization_service = DocumentVectorizationService(settings)

        async with AsyncSessionFactory() as session:
            repo = DocumentsRepository(session)

            document = await repo.get_document_by_id(document_id)
            if document is None:
                return

            await repo.update_extraction_status(
                document_id,
                status_value="processing",
                extraction_error=None,
                extracted_at=document.extracted_at,
            )
            await session.commit()

            try:
                embedded_count = await DocumentsService._vectorize_document_chunks(
                    repo=repo,
                    vectorization_service=vectorization_service,
                    document_id=document_id,
                    batch_size=settings.embedding_batch_size,
                )
                await repo.update_extraction_status(
                    document_id,
                    status_value="completed",
                    extraction_error=None,
                    extracted_at=datetime.now(UTC),
                )
                await session.commit()
                logger.info("Document %s re-vectorized chunks: %s", document_id, embedded_count)
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                await repo.update_extraction_status(
                    document_id,
                    status_value="failed",
                    extraction_error=str(exc)[:1000],
                    extracted_at=datetime.now(UTC),
                )
                await session.commit()

    @staticmethod
    async def _vectorize_document_chunks(
        *,
        repo: DocumentsRepository,
        vectorization_service: DocumentVectorizationService,
        document_id: uuid.UUID,
        batch_size: int,
    ) -> int:
        total_embedded = 0
        current_batch_size = max(batch_size, 1)

        while True:
            chunks = await repo.get_unembedded_chunks(document_id, limit=current_batch_size)
            if not chunks:
                return total_embedded

            try:
                embeddings = await vectorization_service.embed_chunks(chunks)
            except Exception as exc:  # noqa: BLE001
                if len(chunks) == 1:
                    chunk = chunks[0]
                    raise RuntimeError(
                        f"Embedding failed for document {document_id}, chunk {chunk.id}, "
                        f"page {chunk.page_number}, index {chunk.chunk_index}: {exc}"
                    ) from exc

                new_batch_size = max(1, len(chunks) // 2)
                logger.warning(
                    "Embedding batch failed for document %s with size %s. Reducing batch size to %s. Error: %s",
                    document_id,
                    len(chunks),
                    new_batch_size,
                    exc,
                )
                current_batch_size = new_batch_size
                continue

            embedded_now = await repo.bulk_update_embeddings(embeddings)
            await repo.session.commit()
            total_embedded += embedded_now

            if current_batch_size < batch_size:
                current_batch_size = min(batch_size, current_batch_size * 2)

    def _build_object_key(self, user_id: uuid.UUID, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".pdf"
        stem = self._slugify_for_object_key(Path(filename).stem)
        return f"users/{user_id}/documents/{uuid.uuid4().hex}_{stem}{suffix}"

    def _build_title(self, filename: str) -> str:
        # Keep the original user-facing filename while respecting DB length limits.
        return filename.strip()[:255] or "document.pdf"

    def _slugify_for_object_key(self, name: str) -> str:
        # NFKD does not decompose Vietnamese Đ/đ, so map it explicitly first.
        name = name.replace("Đ", "D").replace("đ", "d")
        normalized = unicodedata.normalize("NFKD", name)
        ascii_name = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name.strip())
        return slug.strip("-_.").lower()[:120] or "document"
