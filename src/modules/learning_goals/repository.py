import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.goal_progress_log import GoalProgressLog
from src.models.learning_goal import LearningGoal
from src.models.reminder_event import ReminderEvent
from src.models.reminder_preference import ReminderPreference
from src.models.user import User


class LearningGoalsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_goal(
        self,
        *,
        user_id: uuid.UUID,
        document_id: uuid.UUID | None,
        title: str,
        description: str | None,
        recurrence_type: str,
        period_start: date,
        period_end: date,
        target_date: date,
        milestones: list[dict] | None,
        reminder_enabled: bool,
        progress: int,
        status: str,
        completed_at: datetime | None,
    ) -> LearningGoal:
        goal = LearningGoal(
            user_id=user_id,
            document_id=document_id,
            title=title,
            description=description,
            recurrence_type=recurrence_type,
            period_start=period_start,
            period_end=period_end,
            target_date=target_date,
            milestones=milestones,
            reminder_enabled=reminder_enabled,
            progress=progress,
            status=status,
            completed_at=completed_at,
        )
        self.session.add(goal)
        await self.session.flush()
        return goal

    async def get_user_goal(self, goal_id: uuid.UUID, user_id: uuid.UUID) -> LearningGoal | None:
        query = select(LearningGoal).where(LearningGoal.id == goal_id, LearningGoal.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_user_goals(
        self,
        *,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        status: str | None,
        recurrence_type: str | None,
        document_id: uuid.UUID | None,
        due_from: date | None,
        due_to: date | None,
    ) -> list[LearningGoal]:
        query = select(LearningGoal).where(LearningGoal.user_id == user_id)

        if status is not None:
            query = query.where(LearningGoal.status == status)
        if recurrence_type is not None:
            query = query.where(LearningGoal.recurrence_type == recurrence_type)
        if document_id is not None:
            query = query.where(LearningGoal.document_id == document_id)
        if due_from is not None:
            query = query.where(LearningGoal.target_date >= due_from)
        if due_to is not None:
            query = query.where(LearningGoal.target_date <= due_to)

        query = query.order_by(LearningGoal.target_date.asc(), LearningGoal.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_goal(self, goal: LearningGoal) -> None:
        await self.session.delete(goal)
        await self.session.flush()

    async def create_progress_log(
        self,
        *,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        previous_progress: int | None,
        new_progress: int,
        note: str | None,
    ) -> GoalProgressLog:
        log = GoalProgressLog(
            goal_id=goal_id,
            user_id=user_id,
            previous_progress=previous_progress,
            new_progress=new_progress,
            note=note,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_goal_progress_logs(
        self,
        *,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[GoalProgressLog]:
        query = (
            select(GoalProgressLog)
            .where(GoalProgressLog.goal_id == goal_id, GoalProgressLog.user_id == user_id)
            .order_by(GoalProgressLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_or_create_reminder_preference(self, user_id: uuid.UUID) -> ReminderPreference:
        query = select(ReminderPreference).where(ReminderPreference.user_id == user_id)
        result = await self.session.execute(query)
        preference = result.scalar_one_or_none()
        if preference is not None:
            return preference

        preference = ReminderPreference(user_id=user_id)
        self.session.add(preference)
        await self.session.flush()
        return preference

    async def list_user_reminder_events(
        self,
        *,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        channel: str | None,
    ) -> list[ReminderEvent]:
        query = select(ReminderEvent).where(ReminderEvent.user_id == user_id)
        if channel is not None:
            query = query.where(ReminderEvent.channel == channel)

        query = query.order_by(ReminderEvent.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_reminder_event(
        self,
        *,
        user_id: uuid.UUID,
        goal_id: uuid.UUID | None,
        channel: str,
        event_type: str,
        status: str,
        scheduled_for: datetime,
        payload: dict | None,
    ) -> ReminderEvent:
        event = ReminderEvent(
            user_id=user_id,
            goal_id=goal_id,
            channel=channel,
            event_type=event_type,
            status=status,
            scheduled_for=scheduled_for,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_goals_with_preferences(self) -> list[tuple[LearningGoal, ReminderPreference | None, str]]:
        query = (
            select(LearningGoal, ReminderPreference, User.email)
            .join(User, User.id == LearningGoal.user_id)
            .outerjoin(ReminderPreference, ReminderPreference.user_id == LearningGoal.user_id)
            .where(
                LearningGoal.reminder_enabled.is_(True),
                LearningGoal.status.in_(["in_progress", "overdue"]),
            )
        )
        result = await self.session.execute(query)
        return list(result.all())

    async def has_recent_goal_event(
        self,
        *,
        goal_id: uuid.UUID,
        event_type: str,
        channel: str,
        lookback_hours: int,
    ) -> bool:
        now_at = datetime.now(UTC)
        cutoff = now_at - timedelta(hours=lookback_hours)
        query = select(func.count(ReminderEvent.id)).where(
            ReminderEvent.goal_id == goal_id,
            ReminderEvent.event_type == event_type,
            ReminderEvent.channel == channel,
            ReminderEvent.created_at >= cutoff,
            ReminderEvent.status.in_(["pending", "sent"]),
        )
        result = await self.session.execute(query)
        count = result.scalar_one()
        return count > 0

    async def mark_goal_last_reminded(self, goal_id: uuid.UUID, reminded_at: datetime) -> None:
        query = select(LearningGoal).where(LearningGoal.id == goal_id)
        result = await self.session.execute(query)
        goal = result.scalar_one_or_none()
        if goal is None:
            return

        goal.last_reminded_at = reminded_at
        await self.session.flush()

    async def list_pending_email_events(self, *, now_at: datetime, limit: int) -> list[ReminderEvent]:
        query = (
            select(ReminderEvent)
            .where(
                ReminderEvent.channel == "email",
                ReminderEvent.status == "pending",
                ReminderEvent.scheduled_for <= now_at,
                ReminderEvent.retry_count <= 3,
            )
            .order_by(ReminderEvent.scheduled_for.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_email(self, user_id: uuid.UUID) -> str | None:
        query = select(User.email).where(User.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def mark_event_sent(self, event: ReminderEvent, sent_at: datetime) -> None:
        event.status = "sent"
        event.sent_at = sent_at
        event.error_message = None
        await self.session.flush()

    async def mark_event_failed(self, event: ReminderEvent, error_message: str) -> None:
        event.status = "failed"
        event.retry_count = event.retry_count + 1
        event.error_message = error_message[:1000]
        await self.session.flush()

    async def list_preferences_with_user_email(self) -> list[tuple[ReminderPreference, str]]:
        query = select(ReminderPreference, User.email).join(User, User.id == ReminderPreference.user_id)
        result = await self.session.execute(query)
        return list(result.all())

    async def has_recent_digest_event(self, *, user_id: uuid.UUID, lookback_hours: int) -> bool:
        now_at = datetime.now(UTC)
        cutoff = now_at - timedelta(hours=lookback_hours)
        query = select(func.count(ReminderEvent.id)).where(
            ReminderEvent.user_id == user_id,
            ReminderEvent.event_type == "digest",
            ReminderEvent.created_at >= cutoff,
            ReminderEvent.status.in_(["pending", "sent"]),
        )
        result = await self.session.execute(query)
        count = result.scalar_one()
        return count > 0

    async def count_goal_stats_for_user(self, *, user_id: uuid.UUID, today: date, week_end: date) -> dict[str, int]:
        query = (
            select(
                func.count(LearningGoal.id).filter(LearningGoal.status == "in_progress"),
                func.count(LearningGoal.id).filter(LearningGoal.status == "completed"),
                func.count(LearningGoal.id).filter(LearningGoal.status == "overdue"),
                func.count(LearningGoal.id).filter(LearningGoal.target_date == today),
                func.count(LearningGoal.id).filter(
                    and_(
                        LearningGoal.target_date >= today,
                        LearningGoal.target_date <= week_end,
                        LearningGoal.status.in_(["in_progress", "overdue"]),
                    )
                ),
            )
            .where(LearningGoal.user_id == user_id)
        )
        result = await self.session.execute(query)
        in_progress, completed, overdue, due_today, due_this_week = result.one()
        return {
            "in_progress_count": int(in_progress or 0),
            "completed_count": int(completed or 0),
            "overdue_count": int(overdue or 0),
            "due_today_count": int(due_today or 0),
            "due_this_week_count": int(due_this_week or 0),
        }

    async def list_active_goals_for_user(self, *, user_id: uuid.UUID) -> list[LearningGoal]:
        query = (
            select(LearningGoal)
            .where(
                LearningGoal.user_id == user_id,
                or_(LearningGoal.status == "in_progress", LearningGoal.status == "overdue"),
            )
            .order_by(LearningGoal.target_date.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
