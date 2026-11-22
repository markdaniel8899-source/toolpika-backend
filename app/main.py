"""FastAPI application entrypoint for the Toolpika backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.config import CORS_ORIGINS, settings
from app.pipelines import cron_scheduler
from app.services import queue
from app.studio.service import StudioError

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


@app.exception_handler(StudioError)
async def studio_error_handler(_request: Request, exc: StudioError) -> JSONResponse:
    """Turn expected studio workflow errors into readable 400 responses."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "data": exc.details},
    )
