import re
import unicodedata
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.minio_client import MinioStorageClient
from src.models.user import User
from src.modules.documents.repository import DocumentsRepository
from src.modules.documents.schemas import DocumentDownloadResponse, DocumentUploadResponse

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}


class DocumentsService:
    def __init__(self, session: AsyncSession, minio_client: MinioStorageClient):
        self.session = session
        self.repo = DocumentsRepository(session)
        self.minio_client = minio_client

    async def upload_document(self, *, current_user: User, file: UploadFile) -> DocumentUploadResponse:
        filename = file.filename or "document.pdf"
        content_type = file.content_type or ""

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF files are allowed")

        content = await file.read()
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
