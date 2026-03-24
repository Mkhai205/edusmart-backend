import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.config import get_settings
from src.modules.learning_goals.service import LearningGoalsService

logger = logging.getLogger("uvicorn.error")
_scheduler: AsyncIOScheduler | None = None


async def start_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    settings = get_settings()
    if not settings.reminder_scheduler_enabled:
        logger.info("Reminder scheduler is disabled")
        return

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        LearningGoalsService.run_reminder_scan_job,
        trigger="interval",
        minutes=settings.reminder_scan_interval_minutes,
        id="learning_goal_reminder_scan",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        LearningGoalsService.run_digest_queue_job,
        trigger="interval",
        minutes=settings.reminder_digest_scan_interval_minutes,
        id="learning_goal_digest_queue",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        LearningGoalsService.run_email_dispatch_job,
        trigger="interval",
        minutes=settings.reminder_email_dispatch_interval_minutes,
        id="learning_goal_email_dispatch",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("Reminder scheduler started")


async def stop_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Reminder scheduler stopped")
