"""Cron jobs for the research scout. No build/QA/translation jobs exist."""

from __future__ import annotations

from datetime import timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.pipelines.research_scout import run_research_scout

log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone=timezone.utc)


async def daily_research() -> None:
    """Run the scout once and keep the scheduler alive on failure."""
    log.info("cron_research_scout_started")
    try:
        result = await run_research_scout()
        log.info("cron_research_scout_finished", ideas=len(result.ideas))
    except Exception as exc:  # noqa: BLE001 - scheduler must not die
        log.error("cron_research_scout_failed", error=str(exc))


def start_scheduler() -> None:
    """Start the scheduler and register the daily 03:00 UTC job."""
    if not settings.cron_research_enabled:
        log.info("cron_research_scout_disabled")
        return
    try:
        trigger = CronTrigger.from_crontab(
            settings.cron_research_schedule, timezone=timezone.utc
        )
    except Exception:  # noqa: BLE001 - fall back to the documented default
        log.warning(
            "invalid_cron_schedule",
            value=settings.cron_research_schedule,
            fallback="0 3 * * *",
        )
        trigger = CronTrigger(hour=3, minute=0, timezone=timezone.utc)

    scheduler.add_job(
        daily_research,
        trigger=trigger,
        id="cron:research_scout",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    log.info("cron_research_scout_installed", schedule=settings.cron_research_schedule)


def stop_scheduler() -> None:
    """Stop the scheduler during application shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("cron_scheduler_stopped")
