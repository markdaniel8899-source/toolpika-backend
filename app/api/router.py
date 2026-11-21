"""Top-level API router."""

from fastapi import APIRouter

from app.api.endpoints import admin, health, pipeline, tools

router = APIRouter()
router.include_router(health.router)
router.include_router(pipeline.router)
router.include_router(tools.router)
router.include_router(admin.router)
