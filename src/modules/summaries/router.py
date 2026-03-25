import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user
from src.infrastructure.database.session import get_db_session
from src.models.user import User
from src.modules.summaries.schemas import (
    DocumentSummaryQueuedResponse,
    DocumentSummaryRequest,
    DocumentSummaryStatusResponse,
)
from src.modules.summaries.service import SummariesService

router = APIRouter(prefix="/documents", tags=["summaries"])


@router.post("/{document_id}/summary", response_model=DocumentSummaryQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_document_summary(
    document_id: uuid.UUID,
    payload: DocumentSummaryRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DocumentSummaryQueuedResponse:
    service = SummariesService(session=session)
    response = await service.queue_summary_generation(
        document_id=document_id,
        mode=payload.mode,
        start_page=payload.start_page,
        end_page=payload.end_page,
        keywords=payload.keywords,
        search_limit=payload.search_limit,
        min_similarity=payload.min_similarity,
        current_user=current_user,
    )
    background_tasks.add_task(SummariesService.run_summary_pipeline, response.summary_id)
    return response


@router.get("/{document_id}/summary/latest", response_model=DocumentSummaryStatusResponse)
async def get_document_latest_summary_status(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DocumentSummaryStatusResponse:
    service = SummariesService(session=session)
    return await service.get_latest_summary_status(
        document_id=document_id,
        current_user=current_user,
    )


@router.get("/{document_id}/summary/{summary_id}", response_model=DocumentSummaryStatusResponse)
async def get_document_summary_status(
    document_id: uuid.UUID,
    summary_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DocumentSummaryStatusResponse:
    service = SummariesService(session=session)
    return await service.get_summary_status(
        document_id=document_id,
        summary_id=summary_id,
        current_user=current_user,
    )
