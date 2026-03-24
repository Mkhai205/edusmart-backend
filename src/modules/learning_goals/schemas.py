import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class GoalRecurrenceType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class GoalStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    ARCHIVED = "archived"


class ReminderChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"


class ReminderEventType(str, Enum):
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    DIGEST = "digest"


class ReminderEventStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class LearningGoalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    document_id: uuid.UUID | None = None
    recurrence_type: GoalRecurrenceType
    target_date: date
    milestones: list[dict] | None = None
    reminder_enabled: bool = True


class LearningGoalUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    document_id: uuid.UUID | None = None
    recurrence_type: GoalRecurrenceType | None = None
    target_date: date | None = None
    milestones: list[dict] | None = None
    reminder_enabled: bool | None = None
    status: GoalStatus | None = None


class LearningGoalProgressUpdateRequest(BaseModel):
    progress: int = Field(ge=0, le=100)
    note: str | None = Field(default=None, max_length=1000)


class LearningGoalFilter(BaseModel):
    status: GoalStatus | None = None
    recurrence_type: GoalRecurrenceType | None = None
    document_id: uuid.UUID | None = None
    due_from: date | None = None
    due_to: date | None = None


class LearningGoalResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    document_id: uuid.UUID | None
    title: str
    description: str | None
    recurrence_type: GoalRecurrenceType
    period_start: date
    period_end: date
    target_date: date
    progress: int
    status: GoalStatus
    milestones: list[dict] | None
    reminder_enabled: bool
    last_reminded_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoalProgressLogResponse(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    user_id: uuid.UUID
    previous_progress: int | None
    new_progress: int
    note: str | None
    created_at: datetime


class ReminderPreferenceResponse(BaseModel):
    timezone: str
    email_digest_enabled: bool
    digest_hour: int
    digest_minute: int
    due_soon_hours: int
    overdue_cooldown_hours: int


class ReminderPreferenceUpdateRequest(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    email_digest_enabled: bool | None = None
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    digest_minute: int | None = Field(default=None, ge=0, le=59)
    due_soon_hours: int | None = Field(default=None, ge=1, le=168)
    overdue_cooldown_hours: int | None = Field(default=None, ge=1, le=168)


class ReminderFeedItemResponse(BaseModel):
    event_id: uuid.UUID
    goal_id: uuid.UUID | None
    channel: ReminderChannel
    event_type: ReminderEventType
    status: ReminderEventStatus
    scheduled_for: datetime
    sent_at: datetime | None
    payload: dict | None
    created_at: datetime


class LearningGoalDashboardResponse(BaseModel):
    in_progress_count: int
    completed_count: int
    overdue_count: int
    due_today_count: int
    due_this_week_count: int


class MilestoneSuggestionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    desired_count: int = Field(default=5, ge=3, le=10)


class MilestoneSuggestionResponse(BaseModel):
    milestones: list[dict]
