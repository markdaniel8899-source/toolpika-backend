"""FastAPI application entrypoint for the research-scout backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config import CORS_ORIGINS, settings
from app.pipelines import cron_scheduler

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Start and stop the daily research job around the app lifetime."""
    settings.validate_required()
    cron_scheduler.start_scheduler()
    log.info("application_started", env=settings.app_env)
    yield
    cron_scheduler.stop_scheduler()
    log.info("application_stopped")


app = FastAPI(
    title="Toolpika Research Scout",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
