"""Liveness and readiness endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.config import settings
from app.api.models.responses import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])
STARTED_AT = time.monotonic()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return process liveness and uptime."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime=round(time.monotonic() - STARTED_AT, 2),
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Report whether required provider credentials are configured."""
    checks = {
        "supabase": bool(settings.supabase_url and settings.supabase_service_role_key),
        "tavily": bool(settings.tavily_api_key),
        "nemotron": bool(settings.nvidia_nim_api_key),
    }
    return ReadyResponse(ready=all(checks.values()), checks=checks)
