import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user
from src.infrastructure.database.session import get_db_session
from src.models.user import User
from src.modules.quizzes.schemas import (
    QuizAttemptListItemResponse,
    QuizDetailResponse,
    QuizGenerateRequest,
    QuizListItemResponse,
    QuizQueuedResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from src.modules.quizzes.service import QuizzesService

router = APIRouter(prefix="/learning/quizzes", tags=["quizzes"])


@router.get("", response_model=list[QuizListItemResponse])
async def list_quizzes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    document_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[QuizListItemResponse]:
    service = QuizzesService(session=session)
    return await service.list_quizzes(
        current_user=current_user,
        limit=limit,
        offset=offset,
        document_id=document_id,
    )


@router.post("/generate", response_model=QuizQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_quiz_generation(
    payload: QuizGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuizQueuedResponse:
    service = QuizzesService(session=session)
    response = await service.queue_quiz_generation(payload=payload, current_user=current_user)
    background_tasks.add_task(QuizzesService.run_quiz_pipeline, response.quiz_id)
    return response


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz_detail(
    quiz_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuizDetailResponse:
    service = QuizzesService(session=session)
    return await service.get_quiz_detail(quiz_id=quiz_id, current_user=current_user)


@router.post("/{quiz_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    quiz_id: uuid.UUID,
    payload: QuizSubmitRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuizSubmitResponse:
    service = QuizzesService(session=session)
    return await service.submit_quiz(quiz_id=quiz_id, payload=payload, current_user=current_user)


@router.get("/{quiz_id}/attempts", response_model=list[QuizAttemptListItemResponse])
async def list_quiz_attempts(
    quiz_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[QuizAttemptListItemResponse]:
    service = QuizzesService(session=session)
    return await service.list_quiz_attempts(
        quiz_id=quiz_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
