"""Cron jobs for autonomous research and failed-job retries."""

from __future__ import annotations

import asyncio

import structlog

from app.config import settings
from app.pipelines.orchestrator import run_full_pipeline
from app.services import queue, supabase_client

log = structlog.get_logger(__name__)


async def research_and_build() -> None:
    """Run the autonomous daily research and build job."""
    log.info("cron_research_started")
    result = await run_full_pipeline()
    log.info("cron_research_finished", success=result.success, stage=result.stage)


async def check_failed_jobs_and_retry() -> None:
    """Retry tools that previously failed QA."""
    try:
        rows = supabase_client.select("tool_specs", "slug,status")
    except Exception as exc:  # noqa: BLE001
        log.warning("cron_retry_lookup_failed", error=str(exc))
        return
    failed = [row["slug"] for row in rows if row.get("status") == "qa_failed"]
    for slug in failed:
        log.info("cron_retrying_tool", slug=slug)
        await run_full_pipeline(slug)
        await asyncio.sleep(0)


def install_jobs() -> None:
    """Register cron jobs on the shared scheduler."""
    if not settings.cron_research_enabled:
        log.info("cron_research_disabled")
        return
    parts = settings.cron_research_schedule.split()
    if len(parts) != 5:
        log.warning("invalid_cron_schedule", value=settings.cron_research_schedule)
        return
    minute, hour, day, month, day_of_week = parts
    queue.scheduler.add_job(
        research_and_build,
        trigger="cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        id="cron:research",
        replace_existing=True,
    )
    queue.scheduler.add_job(
        check_failed_jobs_and_retry,
        trigger="interval",
        hours=6,
        id="cron:retry",
        replace_existing=True,
    )
    log.info("cron_jobs_installed", schedule=settings.cron_research_schedule)
