import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user
from src.infrastructure.database.session import get_db_session
from src.models.user import User
from src.modules.learning_goals.schemas import (
    GoalProgressLogResponse,
    GoalRecurrenceType,
    GoalStatus,
    LearningGoalCreateRequest,
    LearningGoalDashboardResponse,
    LearningGoalProgressUpdateRequest,
    LearningGoalResponse,
    LearningGoalUpdateRequest,
    MilestoneSuggestionRequest,
    MilestoneSuggestionResponse,
    ReminderChannel,
    ReminderFeedItemResponse,
    ReminderPreferenceResponse,
    ReminderPreferenceUpdateRequest,
)
from src.modules.learning_goals.service import LearningGoalsService

router = APIRouter(prefix="/learning/goals", tags=["learning-goals"])


@router.post("", response_model=LearningGoalResponse, status_code=status.HTTP_201_CREATED)
async def create_learning_goal(
    payload: LearningGoalCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LearningGoalResponse:
    service = LearningGoalsService(session=session)
    return await service.create_goal(payload=payload, current_user=current_user)


@router.get("", response_model=list[LearningGoalResponse])
async def list_learning_goals(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: GoalStatus | None = Query(default=None, alias="status"),
    recurrence_type: GoalRecurrenceType | None = Query(default=None),
    document_id: uuid.UUID | None = Query(default=None),
    due_from: date | None = Query(default=None),
    due_to: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[LearningGoalResponse]:
    service = LearningGoalsService(session=session)
    return await service.list_goals(
        current_user=current_user,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        recurrence_type=recurrence_type,
        document_id=document_id,
        due_from=due_from,
        due_to=due_to,
    )


@router.get("/dashboard/overview", response_model=LearningGoalDashboardResponse)
async def get_learning_goal_dashboard(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LearningGoalDashboardResponse:
    service = LearningGoalsService(session=session)
    return await service.get_dashboard_overview(current_user=current_user)


@router.get("/reminders/feed", response_model=list[ReminderFeedItemResponse])
async def list_reminder_feed(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    channel: ReminderChannel | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[ReminderFeedItemResponse]:
    service = LearningGoalsService(session=session)
    return await service.list_reminder_feed(
        current_user=current_user,
        limit=limit,
        offset=offset,
        channel=channel,
    )


@router.get("/reminders/preferences", response_model=ReminderPreferenceResponse)
async def get_reminder_preferences(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ReminderPreferenceResponse:
    service = LearningGoalsService(session=session)
    return await service.get_reminder_preferences(current_user=current_user)


@router.patch("/reminders/preferences", response_model=ReminderPreferenceResponse)
async def update_reminder_preferences(
    payload: ReminderPreferenceUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ReminderPreferenceResponse:
    service = LearningGoalsService(session=session)
    return await service.update_reminder_preferences(payload=payload, current_user=current_user)


@router.post("/milestones/suggestions", response_model=MilestoneSuggestionResponse)
async def suggest_learning_goal_milestones(
    payload: MilestoneSuggestionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MilestoneSuggestionResponse:
    _ = current_user
    service = LearningGoalsService(session=session)
    return await service.suggest_milestones(payload=payload)


@router.get("/{goal_id}", response_model=LearningGoalResponse)
async def get_learning_goal(
    goal_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LearningGoalResponse:
    service = LearningGoalsService(session=session)
    return await service.get_goal_detail(goal_id=goal_id, current_user=current_user)


@router.patch("/{goal_id}", response_model=LearningGoalResponse)
async def update_learning_goal(
    goal_id: uuid.UUID,
    payload: LearningGoalUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LearningGoalResponse:
    service = LearningGoalsService(session=session)
    return await service.update_goal(goal_id=goal_id, payload=payload, current_user=current_user)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learning_goal(
    goal_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = LearningGoalsService(session=session)
    await service.delete_goal(goal_id=goal_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{goal_id}/progress", response_model=LearningGoalResponse)
async def update_learning_goal_progress(
    goal_id: uuid.UUID,
    payload: LearningGoalProgressUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LearningGoalResponse:
    service = LearningGoalsService(session=session)
    return await service.update_goal_progress(goal_id=goal_id, payload=payload, current_user=current_user)


@router.get("/{goal_id}/progress", response_model=list[GoalProgressLogResponse])
async def list_learning_goal_progress_logs(
    goal_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[GoalProgressLogResponse]:
    service = LearningGoalsService(session=session)
    return await service.list_goal_progress_logs(
        goal_id=goal_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
