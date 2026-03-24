"""create learning goals and reminders tables

Revision ID: 20260323_01
Revises: 20260322_06
Create Date: 2026-03-23 11:10:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260323_01"
down_revision: str | None = "20260322_06"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("recurrence_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("milestones", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_learning_goals_progress_range"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_goals_user_id"), "learning_goals", ["user_id"], unique=False)
    op.create_index(op.f("ix_learning_goals_document_id"), "learning_goals", ["document_id"], unique=False)
    op.create_index(op.f("ix_learning_goals_target_date"), "learning_goals", ["target_date"], unique=False)
    op.create_index(op.f("ix_learning_goals_status"), "learning_goals", ["status"], unique=False)
    op.create_index(op.f("ix_learning_goals_recurrence_type"), "learning_goals", ["recurrence_type"], unique=False)
    op.create_index(op.f("ix_learning_goals_period_start"), "learning_goals", ["period_start"], unique=False)
    op.create_index(op.f("ix_learning_goals_period_end"), "learning_goals", ["period_end"], unique=False)
    op.create_index(op.f("ix_learning_goals_created_at"), "learning_goals", ["created_at"], unique=False)
    op.create_index(
        "ix_learning_goals_user_status_target_date",
        "learning_goals",
        ["user_id", "status", "target_date"],
        unique=False,
    )

    op.create_table(
        "goal_progress_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_progress", sa.Integer(), nullable=True),
        sa.Column("new_progress", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("new_progress >= 0 AND new_progress <= 100", name="ck_goal_progress_logs_new_progress_range"),
        sa.ForeignKeyConstraint(["goal_id"], ["learning_goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goal_progress_logs_goal_id"), "goal_progress_logs", ["goal_id"], unique=False)
    op.create_index(op.f("ix_goal_progress_logs_user_id"), "goal_progress_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_goal_progress_logs_created_at"), "goal_progress_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_goal_progress_logs_goal_created_at",
        "goal_progress_logs",
        ["goal_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "reminder_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("email_digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("digest_hour", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("digest_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_soon_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("overdue_cooldown_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("digest_hour >= 0 AND digest_hour <= 23", name="ck_reminder_preferences_digest_hour_range"),
        sa.CheckConstraint("digest_minute >= 0 AND digest_minute <= 59", name="ck_reminder_preferences_digest_minute_range"),
        sa.CheckConstraint("due_soon_hours >= 1 AND due_soon_hours <= 168", name="ck_reminder_preferences_due_soon_hours_range"),
        sa.CheckConstraint(
            "overdue_cooldown_hours >= 1 AND overdue_cooldown_hours <= 168",
            name="ck_reminder_preferences_overdue_cooldown_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_reminder_preferences_user_id"),
    )
    op.create_index(op.f("ix_reminder_preferences_user_id"), "reminder_preferences", ["user_id"], unique=True)

    op.create_table(
        "reminder_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["learning_goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reminder_events_user_id"), "reminder_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_reminder_events_goal_id"), "reminder_events", ["goal_id"], unique=False)
    op.create_index(op.f("ix_reminder_events_status"), "reminder_events", ["status"], unique=False)
    op.create_index(op.f("ix_reminder_events_scheduled_for"), "reminder_events", ["scheduled_for"], unique=False)
    op.create_index(
        "ix_reminder_events_status_scheduled_for",
        "reminder_events",
        ["status", "scheduled_for"],
        unique=False,
    )

    op.alter_column("learning_goals", "progress", server_default=None)
    op.alter_column("learning_goals", "status", server_default=None)
    op.alter_column("learning_goals", "reminder_enabled", server_default=None)
    op.alter_column("reminder_preferences", "timezone", server_default=None)
    op.alter_column("reminder_preferences", "email_digest_enabled", server_default=None)
    op.alter_column("reminder_preferences", "digest_hour", server_default=None)
    op.alter_column("reminder_preferences", "digest_minute", server_default=None)
    op.alter_column("reminder_preferences", "due_soon_hours", server_default=None)
    op.alter_column("reminder_preferences", "overdue_cooldown_hours", server_default=None)
    op.alter_column("reminder_events", "status", server_default=None)
    op.alter_column("reminder_events", "retry_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_reminder_events_status_scheduled_for", table_name="reminder_events")
    op.drop_index(op.f("ix_reminder_events_scheduled_for"), table_name="reminder_events")
    op.drop_index(op.f("ix_reminder_events_status"), table_name="reminder_events")
    op.drop_index(op.f("ix_reminder_events_goal_id"), table_name="reminder_events")
    op.drop_index(op.f("ix_reminder_events_user_id"), table_name="reminder_events")
    op.drop_table("reminder_events")

    op.drop_index(op.f("ix_reminder_preferences_user_id"), table_name="reminder_preferences")
    op.drop_table("reminder_preferences")

    op.drop_index("ix_goal_progress_logs_goal_created_at", table_name="goal_progress_logs")
    op.drop_index(op.f("ix_goal_progress_logs_created_at"), table_name="goal_progress_logs")
    op.drop_index(op.f("ix_goal_progress_logs_user_id"), table_name="goal_progress_logs")
    op.drop_index(op.f("ix_goal_progress_logs_goal_id"), table_name="goal_progress_logs")
    op.drop_table("goal_progress_logs")

    op.drop_index("ix_learning_goals_user_status_target_date", table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_created_at"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_period_end"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_period_start"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_recurrence_type"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_status"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_target_date"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_document_id"), table_name="learning_goals")
    op.drop_index(op.f("ix_learning_goals_user_id"), table_name="learning_goals")
    op.drop_table("learning_goals")
