import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user, get_minio_client
from src.infrastructure.database.session import get_db_session
from src.infrastructure.storage.minio_client import MinioStorageClient
from src.models.user import User
from src.modules.documents.schemas import (
    DocumentDownloadResponse,
    DocumentExtractionStatusResponse,
    DocumentUploadResponse,
)
from src.modules.documents.service import DocumentsService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    minio_client: MinioStorageClient = Depends(get_minio_client),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    service = DocumentsService(session=session, minio_client=minio_client)
    content = await file.read()
    response = await service.upload_document(
        current_user=current_user,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "",
        content=content,
    )
    background_tasks.add_task(
        DocumentsService.run_extraction_pipeline,
        response.document_id,
        response.object_key,
        minio_client,
    )
    return response


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def get_document_download_url(
    document_id: uuid.UUID,
    expires_in_seconds: int = Query(default=900, ge=60, le=3600),
    session: AsyncSession = Depends(get_db_session),
    minio_client: MinioStorageClient = Depends(get_minio_client),
    current_user: User = Depends(get_current_user),
) -> DocumentDownloadResponse:
    service = DocumentsService(session=session, minio_client=minio_client)
    return await service.generate_download_link(
        document_id=document_id,
        current_user=current_user,
        expires_in_seconds=expires_in_seconds,
    )


@router.get("/{document_id}", response_model=DocumentExtractionStatusResponse)
async def get_document_extraction_status(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    minio_client: MinioStorageClient = Depends(get_minio_client),
    current_user: User = Depends(get_current_user),
) -> DocumentExtractionStatusResponse:
    service = DocumentsService(session=session, minio_client=minio_client)
    return await service.get_document_extraction_status(document_id=document_id, current_user=current_user)
