import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user
from src.infrastructure.database.session import get_db_session
from src.models.user import User
from src.modules.flashcards.schemas import (
    FlashcardGenerateRequest,
    FlashcardItemResponse,
    ManualFlashcardCardCreateRequest,
    ManualFlashcardCardUpdateRequest,
    ManualFlashcardSetCreateRequest,
    ManualFlashcardSetResponse,
    ManualFlashcardSetUpdateRequest,
    FlashcardQueuedResponse,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    FlashcardReviewTodayResponse,
    FlashcardSetDetailResponse,
    FlashcardSetListItemResponse,
)
from src.modules.flashcards.service import FlashcardsService

router = APIRouter(prefix="/learning/flashcards", tags=["flashcards"])


@router.post("/manual/sets", response_model=ManualFlashcardSetResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_flashcard_set(
    payload: ManualFlashcardSetCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ManualFlashcardSetResponse:
    service = FlashcardsService(session=session)
    return await service.create_manual_set(payload=payload, current_user=current_user)


@router.patch("/manual/sets/{set_id}", response_model=ManualFlashcardSetResponse)
async def update_manual_flashcard_set(
    set_id: uuid.UUID,
    payload: ManualFlashcardSetUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ManualFlashcardSetResponse:
    service = FlashcardsService(session=session)
    return await service.update_manual_set(set_id=set_id, payload=payload, current_user=current_user)


@router.delete("/manual/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual_flashcard_set(
    set_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = FlashcardsService(session=session)
    await service.delete_manual_set(set_id=set_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/manual/sets/{set_id}/cards", response_model=FlashcardItemResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_flashcard_card(
    set_id: uuid.UUID,
    payload: ManualFlashcardCardCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FlashcardItemResponse:
    service = FlashcardsService(session=session)
    return await service.create_manual_card(set_id=set_id, payload=payload, current_user=current_user)


@router.patch("/manual/cards/{card_id}", response_model=FlashcardItemResponse)
async def update_manual_flashcard_card(
    card_id: uuid.UUID,
    payload: ManualFlashcardCardUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FlashcardItemResponse:
    service = FlashcardsService(session=session)
    return await service.update_manual_card(card_id=card_id, payload=payload, current_user=current_user)


@router.delete("/manual/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual_flashcard_card(
    card_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = FlashcardsService(session=session)
    await service.delete_manual_card(card_id=card_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[FlashcardSetListItemResponse])
async def list_flashcard_sets(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    document_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[FlashcardSetListItemResponse]:
    service = FlashcardsService(session=session)
    return await service.list_flashcard_sets(
        current_user=current_user,
        limit=limit,
        offset=offset,
        document_id=document_id,
    )


@router.post("/generate", response_model=FlashcardQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_flashcard_generation(
    payload: FlashcardGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FlashcardQueuedResponse:
    service = FlashcardsService(session=session)
    response = await service.queue_flashcard_generation(payload=payload, current_user=current_user)
    background_tasks.add_task(FlashcardsService.run_flashcard_pipeline, response.set_id)
    return response


@router.get("/review/today", response_model=list[FlashcardReviewTodayResponse])
async def list_due_flashcards_today(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    set_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[FlashcardReviewTodayResponse]:
    service = FlashcardsService(session=session)
    return await service.list_due_cards_today(
        current_user=current_user,
        limit=limit,
        offset=offset,
        set_id=set_id,
    )


@router.post("/cards/{card_id}/review", response_model=FlashcardReviewResponse)
async def review_flashcard(
    card_id: uuid.UUID,
    payload: FlashcardReviewRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FlashcardReviewResponse:
    service = FlashcardsService(session=session)
    return await service.review_card(card_id=card_id, payload=payload, current_user=current_user)


@router.get("/{set_id}", response_model=FlashcardSetDetailResponse)
async def get_flashcard_set_detail(
    set_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FlashcardSetDetailResponse:
    service = FlashcardsService(session=session)
    return await service.get_flashcard_set_detail(set_id=set_id, current_user=current_user)


@router.get("/{set_id}/cards", response_model=list[FlashcardItemResponse])
async def list_flashcards_in_set(
    set_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[FlashcardItemResponse]:
    service = FlashcardsService(session=session)
    return await service.list_set_cards(
        set_id=set_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
