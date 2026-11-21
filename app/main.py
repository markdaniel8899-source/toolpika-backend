"""FastAPI application entrypoint for the Toolpika backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config import CORS_ORIGINS, settings
from app.pipelines import cron_scheduler
from app.services import queue

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start and stop the scheduler around the application lifetime."""
    settings.validate_required()
    queue.start_scheduler()
    cron_scheduler.install_jobs()
    log.info("application_started", env=settings.app_env)
    yield
    queue.stop_scheduler()
    log.info("application_stopped")


app = FastAPI(
    title="Toolpika Backend",
    version="1.0.0",
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
