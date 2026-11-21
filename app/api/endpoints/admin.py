"""Admin dashboard, logs and manual cron triggers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.models.responses import ConfigResponse
from app.config import settings
from app.pipelines import cron_scheduler
from app.services import queue, supabase_client

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/pipeline-status")
async def pipeline_status() -> dict[str, Any]:
    """Return queue depth and the most recent pipeline runs."""
    try:
        runs = supabase_client.select(
            "pipeline_runs", "stage,status,details,created_at"
        )[-10:]
    except Exception:  # noqa: BLE001 - admin view must not fail on missing table
        runs = []
    return {"queue_depth": queue.queue_depth(), "recent_runs": runs}


@router.get("/logs")
async def logs(
    stage: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Return filtered pipeline log rows."""
    try:
        rows = supabase_client.select("pipeline_runs", "stage,status,details,created_at")
    except Exception:  # noqa: BLE001
        return []
    if stage:
        rows = [row for row in rows if row.get("stage") == stage]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return rows[-limit:]


@router.post("/trigger-cron")
async def trigger_cron() -> dict[str, Any]:
    """Manually run the daily research job."""
    await cron_scheduler.research_and_build()
    return {"success": True, "detail": "cron triggered"}


@router.get("/config", response_model=ConfigResponse)
async def public_config() -> ConfigResponse:
    """Expose safe pipeline settings to the frontend."""
    return ConfigResponse(**settings.public_config())
