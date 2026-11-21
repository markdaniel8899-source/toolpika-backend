"""Delayed job queue backed by APScheduler with an in-process fallback."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")
_jobs: dict[str, dict[str, Any]] = {}


def start_scheduler() -> None:
    """Start the in-process scheduler once at application startup."""
    if not scheduler.running:
        scheduler.start()
        log.info("scheduler_started")


def stop_scheduler() -> None:
    """Stop the scheduler during application shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def schedule_after(minutes: float, job_id: str, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> str:
    """Schedule a coroutine to run after a delay; return the job id."""
    run_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    _jobs[job_id] = {"run_at": run_at.isoformat(), "status": "queued"}
    scheduler.add_job(
        func,
        trigger="date",
        run_date=run_at,
        args=args,
        id=job_id,
        replace_existing=True,
    )
    log.info("job_scheduled", job_id=job_id, run_at=run_at.isoformat())
    return job_id


def queue_depth() -> int:
    """Return the number of scheduled jobs."""
    return len(_jobs)


def job_status(job_id: str) -> dict[str, Any] | None:
    """Return the recorded status of a scheduled job."""
    return _jobs.get(job_id)
