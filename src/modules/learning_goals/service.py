import asyncio
import json
import smtplib
import uuid
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.infrastructure.database.session import AsyncSessionFactory
from src.models.learning_goal import LearningGoal
from src.models.reminder_event import ReminderEvent
from src.models.user import User
from src.modules.learning_goals.repository import LearningGoalsRepository
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
    ReminderEventStatus,
    ReminderEventType,
    ReminderFeedItemResponse,
    ReminderPreferenceResponse,
    ReminderPreferenceUpdateRequest,
)


class _LLMMilestonePayload(BaseModel):
    milestones: list[str] = Field(min_length=3)


class LearningGoalsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LearningGoalsRepository(session)

    async def create_goal(self, *, payload: LearningGoalCreateRequest, current_user: User) -> LearningGoalResponse:
        if payload.document_id is not None:
            document = await self.repo.get_user_document(document_id=payload.document_id, user_id=current_user.id)
            if document is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        period_start, period_end = self._period_bounds(payload.recurrence_type, payload.target_date)
        goal_status, completed_at = self._resolve_goal_status(progress=0, target_date=payload.target_date)

        goal = await self.repo.create_goal(
            user_id=current_user.id,
            document_id=payload.document_id,
            title=payload.title,
            description=payload.description,
            recurrence_type=payload.recurrence_type.value,
            period_start=period_start,
            period_end=period_end,
            target_date=payload.target_date,
            milestones=payload.milestones,
            reminder_enabled=payload.reminder_enabled,
            progress=0,
            status=goal_status.value,
            completed_at=completed_at,
        )
        await self.session.commit()
        return self._to_goal_response(goal)

    async def list_goals(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        status_filter: GoalStatus | None,
        recurrence_type: GoalRecurrenceType | None,
        document_id: uuid.UUID | None,
        due_from: date | None,
        due_to: date | None,
    ) -> list[LearningGoalResponse]:
        goals = await self.repo.list_user_goals(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            status=status_filter.value if status_filter is not None else None,
            recurrence_type=recurrence_type.value if recurrence_type is not None else None,
            document_id=document_id,
            due_from=due_from,
            due_to=due_to,
        )
        return [self._to_goal_response(goal) for goal in goals]

    async def get_goal_detail(self, *, goal_id: uuid.UUID, current_user: User) -> LearningGoalResponse:
        goal = await self.repo.get_user_goal(goal_id=goal_id, user_id=current_user.id)
        if goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning goal not found")
        return self._to_goal_response(goal)

    async def update_goal(
        self,
        *,
        goal_id: uuid.UUID,
        payload: LearningGoalUpdateRequest,
        current_user: User,
    ) -> LearningGoalResponse:
        goal = await self.repo.get_user_goal(goal_id=goal_id, user_id=current_user.id)
        if goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning goal not found")

        if payload.document_id is not None:
            document = await self.repo.get_user_document(document_id=payload.document_id, user_id=current_user.id)
            if document is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
            goal.document_id = payload.document_id

        if payload.title is not None:
            goal.title = payload.title
        if payload.description is not None:
            goal.description = payload.description
        if payload.milestones is not None:
            goal.milestones = payload.milestones
        if payload.reminder_enabled is not None:
            goal.reminder_enabled = payload.reminder_enabled

        next_recurrence = payload.recurrence_type or GoalRecurrenceType(goal.recurrence_type)
        next_target_date = payload.target_date or goal.target_date

        goal.recurrence_type = next_recurrence.value
        goal.target_date = next_target_date
        period_start, period_end = self._period_bounds(next_recurrence, next_target_date)
        goal.period_start = period_start
        goal.period_end = period_end

        if payload.status is not None and payload.status == GoalStatus.ARCHIVED:
            goal.status = GoalStatus.ARCHIVED.value
        else:
            derived_status, completed_at = self._resolve_goal_status(progress=goal.progress, target_date=goal.target_date)
            goal.status = derived_status.value
            goal.completed_at = completed_at

        await self.session.commit()
        await self.session.refresh(goal)
        return self._to_goal_response(goal)

    async def delete_goal(self, *, goal_id: uuid.UUID, current_user: User) -> None:
        goal = await self.repo.get_user_goal(goal_id=goal_id, user_id=current_user.id)
        if goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning goal not found")

        await self.repo.delete_goal(goal)
        await self.session.commit()

    async def update_goal_progress(
        self,
        *,
        goal_id: uuid.UUID,
        payload: LearningGoalProgressUpdateRequest,
        current_user: User,
    ) -> LearningGoalResponse:
        goal = await self.repo.get_user_goal(goal_id=goal_id, user_id=current_user.id)
        if goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning goal not found")

        previous_progress = goal.progress
        goal.progress = payload.progress
        goal_status, completed_at = self._resolve_goal_status(progress=goal.progress, target_date=goal.target_date)
        goal.status = goal_status.value
        goal.completed_at = completed_at

        await self.repo.create_progress_log(
            goal_id=goal.id,
            user_id=current_user.id,
            previous_progress=previous_progress,
            new_progress=payload.progress,
            note=payload.note,
        )
        await self.session.commit()
        await self.session.refresh(goal)
        return self._to_goal_response(goal)

    async def list_goal_progress_logs(
        self,
        *,
        goal_id: uuid.UUID,
        current_user: User,
        limit: int,
        offset: int,
    ) -> list[GoalProgressLogResponse]:
        goal = await self.repo.get_user_goal(goal_id=goal_id, user_id=current_user.id)
        if goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning goal not found")

        logs = await self.repo.list_goal_progress_logs(
            goal_id=goal_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
        return [
            GoalProgressLogResponse(
                id=item.id,
                goal_id=item.goal_id,
                user_id=item.user_id,
                previous_progress=item.previous_progress,
                new_progress=item.new_progress,
                note=item.note,
                created_at=item.created_at,
            )
            for item in logs
        ]

    async def get_dashboard_overview(self, *, current_user: User) -> LearningGoalDashboardResponse:
        today = datetime.now(UTC).date()
        week_end = today + timedelta(days=6 - today.weekday())
        stats = await self.repo.count_goal_stats_for_user(user_id=current_user.id, today=today, week_end=week_end)
        return LearningGoalDashboardResponse(**stats)

    async def get_reminder_preferences(self, *, current_user: User) -> ReminderPreferenceResponse:
        preference = await self.repo.get_or_create_reminder_preference(current_user.id)
        await self.session.commit()
        return self._to_preference_response(preference)

    async def update_reminder_preferences(
        self,
        *,
        payload: ReminderPreferenceUpdateRequest,
        current_user: User,
    ) -> ReminderPreferenceResponse:
        preference = await self.repo.get_or_create_reminder_preference(current_user.id)

        if payload.timezone is not None:
            self._validate_timezone(payload.timezone)
            preference.timezone = payload.timezone
        if payload.email_digest_enabled is not None:
            preference.email_digest_enabled = payload.email_digest_enabled
        if payload.digest_hour is not None:
            preference.digest_hour = payload.digest_hour
        if payload.digest_minute is not None:
            preference.digest_minute = payload.digest_minute
        if payload.due_soon_hours is not None:
            preference.due_soon_hours = payload.due_soon_hours
        if payload.overdue_cooldown_hours is not None:
            preference.overdue_cooldown_hours = payload.overdue_cooldown_hours

        await self.session.commit()
        await self.session.refresh(preference)
        return self._to_preference_response(preference)

    async def list_reminder_feed(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        channel: ReminderChannel | None,
    ) -> list[ReminderFeedItemResponse]:
        items = await self.repo.list_user_reminder_events(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            channel=channel.value if channel is not None else None,
        )
        return [self._to_reminder_feed_item(item) for item in items]

    async def suggest_milestones(self, *, payload: MilestoneSuggestionRequest) -> MilestoneSuggestionResponse:
        settings = get_settings()
        if not settings.gemini_api_key:
            return MilestoneSuggestionResponse(milestones=self._fallback_milestones(payload))

        llm = ChatGoogleGenerativeAI(
            model=settings.google_summary_model,
            api_key=settings.gemini_api_key,
            temperature=0.2,
            request_timeout=settings.summary_request_timeout_seconds,
            model_kwargs={"response_mime_type": "application/json"},
        )

        prompt = (
            "Generate concise learning milestones as a JSON object with key 'milestones'. "
            "Each milestone should be a short actionable string. "
            f"Return exactly {payload.desired_count} milestones."
        )
        user_text = f"Title: {payload.title}\nDescription: {payload.description or ''}"

        try:
            response = await llm.ainvoke([("system", prompt), ("human", user_text)])
            content = getattr(response, "content", "")
            text = self._extract_text_content(content)
            parsed = _LLMMilestonePayload.model_validate(json.loads(text))
            milestones = [{"title": item, "completed": False} for item in parsed.milestones[: payload.desired_count]]
            return MilestoneSuggestionResponse(milestones=milestones)
        except (ValidationError, json.JSONDecodeError, ValueError):
            return MilestoneSuggestionResponse(milestones=self._fallback_milestones(payload))

    async def run_reminder_scan(self) -> int:
        now_utc = datetime.now(UTC)
        rows = await self.repo.list_goals_with_preferences()
        created_events = 0

        for goal, preference, _email in rows:
            if goal.status == GoalStatus.COMPLETED.value or goal.status == GoalStatus.ARCHIVED.value:
                continue

            timezone_name = preference.timezone if preference is not None else "UTC"
            due_soon_hours = preference.due_soon_hours if preference is not None else 24
            cooldown_hours = preference.overdue_cooldown_hours if preference is not None else 24

            local_today = now_utc.astimezone(ZoneInfo(timezone_name)).date()
            days_until_due = (goal.target_date - local_today).days

            event_type: ReminderEventType | None = None
            if goal.status in {GoalStatus.IN_PROGRESS.value, GoalStatus.OVERDUE.value}:
                if goal.target_date < local_today:
                    event_type = ReminderEventType.OVERDUE
                elif days_until_due <= max(1, due_soon_hours // 24):
                    event_type = ReminderEventType.DUE_SOON

            if event_type is None:
                continue

            has_recent_in_app = await self.repo.has_recent_goal_event(
                goal_id=goal.id,
                event_type=event_type.value,
                channel=ReminderChannel.IN_APP.value,
                lookback_hours=cooldown_hours,
            )
            if has_recent_in_app:
                continue

            payload = {
                "title": goal.title,
                "target_date": goal.target_date.isoformat(),
                "status": goal.status,
            }
            await self.repo.create_reminder_event(
                user_id=goal.user_id,
                goal_id=goal.id,
                channel=ReminderChannel.IN_APP.value,
                event_type=event_type.value,
                status=ReminderEventStatus.PENDING.value,
                scheduled_for=now_utc,
                payload=payload,
            )
            created_events += 1

            await self.repo.create_reminder_event(
                user_id=goal.user_id,
                goal_id=goal.id,
                channel=ReminderChannel.EMAIL.value,
                event_type=event_type.value,
                status=ReminderEventStatus.PENDING.value,
                scheduled_for=now_utc,
                payload=payload,
            )
            created_events += 1
            await self.repo.mark_goal_last_reminded(goal.id, now_utc)

        await self.session.commit()
        return created_events

    async def queue_daily_digest_events(self) -> int:
        now_utc = datetime.now(UTC)
        created_events = 0
        preferences = await self.repo.list_preferences_with_user_email()

        for preference, _email in preferences:
            if not preference.email_digest_enabled:
                continue

            local_now = now_utc.astimezone(ZoneInfo(preference.timezone))
            if local_now.hour != preference.digest_hour:
                continue
            if abs(local_now.minute - preference.digest_minute) > 10:
                continue

            has_recent = await self.repo.has_recent_digest_event(user_id=preference.user_id, lookback_hours=18)
            if has_recent:
                continue

            goals = await self.repo.list_active_goals_for_user(user_id=preference.user_id)
            if not goals:
                continue

            overdue_count = 0
            due_soon_count = 0
            for goal in goals:
                days_until_due = (goal.target_date - local_now.date()).days
                if days_until_due < 0:
                    overdue_count += 1
                elif days_until_due <= 1:
                    due_soon_count += 1

            if overdue_count == 0 and due_soon_count == 0:
                continue

            payload = {
                "digest_date": local_now.date().isoformat(),
                "overdue_count": overdue_count,
                "due_soon_count": due_soon_count,
            }
            await self.repo.create_reminder_event(
                user_id=preference.user_id,
                goal_id=None,
                channel=ReminderChannel.EMAIL.value,
                event_type=ReminderEventType.DIGEST.value,
                status=ReminderEventStatus.PENDING.value,
                scheduled_for=now_utc,
                payload=payload,
            )
            created_events += 1

        await self.session.commit()
        return created_events

    async def dispatch_pending_email_events(self, limit: int = 50) -> int:
        settings = get_settings()
        if not settings.smtp_host or not settings.smtp_sender_email:
            return 0

        events = await self.repo.list_pending_email_events(now_at=datetime.now(UTC), limit=limit)
        if not events:
            return 0

        sent_count = 0
        for event in events:
            user_email = await self.repo.get_user_email(event.user_id)
            if not user_email:
                await self.repo.mark_event_failed(event, "User email not found")
                continue

            subject, body = self._build_email_content(event)
            try:
                await asyncio.to_thread(
                    self._send_email,
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    smtp_username=settings.smtp_username,
                    smtp_password=settings.smtp_password,
                    use_tls=settings.smtp_use_tls,
                    sender=settings.smtp_sender_email,
                    recipient=user_email,
                    subject=subject,
                    body=body,
                )
                await self.repo.mark_event_sent(event, sent_at=datetime.now(UTC))
                sent_count += 1
            except Exception as exc:  # noqa: BLE001
                await self.repo.mark_event_failed(event, str(exc))

        await self.session.commit()
        return sent_count

    @staticmethod
    async def run_reminder_scan_job() -> int:
        async with AsyncSessionFactory() as session:
            service = LearningGoalsService(session=session)
            return await service.run_reminder_scan()

    @staticmethod
    async def run_digest_queue_job() -> int:
        async with AsyncSessionFactory() as session:
            service = LearningGoalsService(session=session)
            return await service.queue_daily_digest_events()

    @staticmethod
    async def run_email_dispatch_job() -> int:
        async with AsyncSessionFactory() as session:
            service = LearningGoalsService(session=session)
            return await service.dispatch_pending_email_events()

    @staticmethod
    def _send_email(
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str | None,
        smtp_password: str | None,
        use_tls: bool,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if smtp_username and smtp_password:
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)

    def _build_email_content(self, event: ReminderEvent) -> tuple[str, str]:
        payload = event.payload or {}
        if event.event_type == ReminderEventType.DIGEST.value:
            subject = "EduSmart - Daily Learning Goals Digest"
            body = (
                "Daily digest\n"
                f"Due soon goals: {payload.get('due_soon_count', 0)}\n"
                f"Overdue goals: {payload.get('overdue_count', 0)}\n"
            )
            return subject, body

        title = payload.get("title", "Learning goal")
        target_date = payload.get("target_date", "")
        if event.event_type == ReminderEventType.OVERDUE.value:
            subject = "EduSmart - Goal overdue reminder"
            body = f"Goal '{title}' is overdue since {target_date}."
        else:
            subject = "EduSmart - Goal due soon reminder"
            body = f"Goal '{title}' is approaching deadline on {target_date}."
        return subject, body

    def _period_bounds(self, recurrence_type: GoalRecurrenceType, target_date: date) -> tuple[date, date]:
        if recurrence_type == GoalRecurrenceType.DAILY:
            return target_date, target_date

        if recurrence_type == GoalRecurrenceType.WEEKLY:
            start = target_date - timedelta(days=target_date.weekday())
            end = start + timedelta(days=6)
            return start, end

        month_start = target_date.replace(day=1)
        month_end = target_date.replace(day=monthrange(target_date.year, target_date.month)[1])
        return month_start, month_end

    def _resolve_goal_status(self, *, progress: int, target_date: date) -> tuple[GoalStatus, datetime | None]:
        now_utc = datetime.now(UTC)
        today = now_utc.date()
        if progress >= 100:
            return GoalStatus.COMPLETED, now_utc
        if target_date < today:
            return GoalStatus.OVERDUE, None
        return GoalStatus.IN_PROGRESS, None

    def _to_goal_response(self, goal: LearningGoal) -> LearningGoalResponse:
        return LearningGoalResponse(
            id=goal.id,
            user_id=goal.user_id,
            document_id=goal.document_id,
            title=goal.title,
            description=goal.description,
            recurrence_type=GoalRecurrenceType(goal.recurrence_type),
            period_start=goal.period_start,
            period_end=goal.period_end,
            target_date=goal.target_date,
            progress=goal.progress,
            status=GoalStatus(goal.status),
            milestones=goal.milestones,
            reminder_enabled=goal.reminder_enabled,
            last_reminded_at=goal.last_reminded_at,
            completed_at=goal.completed_at,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )

    def _to_preference_response(self, preference) -> ReminderPreferenceResponse:
        return ReminderPreferenceResponse(
            timezone=preference.timezone,
            email_digest_enabled=preference.email_digest_enabled,
            digest_hour=preference.digest_hour,
            digest_minute=preference.digest_minute,
            due_soon_hours=preference.due_soon_hours,
            overdue_cooldown_hours=preference.overdue_cooldown_hours,
        )

    def _to_reminder_feed_item(self, event: ReminderEvent) -> ReminderFeedItemResponse:
        return ReminderFeedItemResponse(
            event_id=event.id,
            goal_id=event.goal_id,
            channel=ReminderChannel(event.channel),
            event_type=ReminderEventType(event.event_type),
            status=ReminderEventStatus(event.status),
            scheduled_for=event.scheduled_for,
            sent_at=event.sent_at,
            payload=event.payload,
            created_at=event.created_at,
        )

    def _validate_timezone(self, timezone_name: str) -> None:
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid timezone") from exc

    def _fallback_milestones(self, payload: MilestoneSuggestionRequest) -> list[dict]:
        base = payload.description.strip() if payload.description else payload.title
        tokens = [item.strip() for item in base.replace("\n", " ").split(".") if item.strip()]
        milestones: list[dict] = []

        for token in tokens:
            milestones.append({"title": token[:120], "completed": False})
            if len(milestones) >= payload.desired_count:
                return milestones

        while len(milestones) < payload.desired_count:
            milestones.append({"title": f"Milestone {len(milestones) + 1}", "completed": False})
        return milestones

    def _extract_text_content(self, content) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            joined = "\n".join(parts).strip()
            if joined:
                return joined
        text = str(content).strip()
        if not text:
            raise ValueError("Empty milestone suggestion content")
        return text
