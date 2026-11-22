"""Tool Studio API: RAG chat, code generation, apply, translation and publish."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from app.api.models.requests import (
    StudioAutoRunRequest,
    StudioChatRequest,
    StudioPlanRequest,
    StudioSessionRequest,
    StudioTranslateRequest,
)
from app.config import settings
from app.studio import service
from app.studio.service import StudioError

router = APIRouter(prefix="/api/studio", tags=["studio"])


def _enabled() -> None:
    if not settings.studio_enabled:
        raise StudioError("Tool Studio is disabled on this deployment.")


@router.get("/config")
async def studio_config() -> dict[str, Any]:
    """Safe Studio configuration for the admin UI."""
    return {
        "enabled": settings.studio_enabled,
        "model": settings.nemotron_model,
        "translation_model": settings.groq_model,
        "locales": settings.locales,
        "qa_max_retries": settings.qa_max_retries,
        "frontend_path_configured": bool(
            settings.studio_frontend_path or service.codegen.resolve_frontend_path()
        ),
        "github_configured": bool(
            settings.github_pat
            and settings.github_repo_owner
            and settings.github_repo_name
        ),
        "github_repo": f"{settings.github_repo_owner}/{settings.github_repo_name}"
        if settings.github_repo_owner and settings.github_repo_name
        else None,
        "github_base_branch": settings.github_base_branch,
        "auto_merge_pr": settings.studio_auto_merge_pr,
    }


@router.post("/sessions")
async def create_session(payload: StudioSessionRequest) -> dict[str, Any]:
    _enabled()
    return service.create_session(payload.title, payload.idea, payload.source_url)


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    _enabled()
    return service.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    _enabled()
    return service.get_session_bundle(session_id)


@router.post("/sessions/{session_id}/chat")
async def chat(session_id: str, payload: StudioChatRequest) -> dict[str, Any]:
    _enabled()
    return await service.chat(session_id, payload.message, payload.auto_plan)


@router.post("/sessions/{session_id}/plan")
async def plan(session_id: str, payload: StudioPlanRequest) -> dict[str, Any]:
    _enabled()
    return await asyncio.to_thread(
        service.research_and_plan, session_id, payload.idea, payload.source_url
    )


@router.post("/sessions/{session_id}/auto-run")
async def auto_run(session_id: str, payload: StudioAutoRunRequest) -> dict[str, Any]:
    """Run research → plan → codegen → apply → translate → publish in one go."""
    _enabled()
    return await service.auto_run(
        session_id, payload.idea, payload.source_url, payload.locales
    )


@router.post("/sessions/{session_id}/generate")
async def generate(session_id: str) -> dict[str, Any]:
    _enabled()
    return await service.generate(session_id)


@router.post("/sessions/{session_id}/apply")
async def apply(session_id: str) -> dict[str, Any]:
    _enabled()
    return await service.apply(session_id)


@router.post("/sessions/{session_id}/translate")
async def translate(
    session_id: str, payload: StudioTranslateRequest
) -> dict[str, Any]:
    _enabled()
    return await service.translate(session_id, payload.locales)


@router.post("/sessions/{session_id}/publish")
async def publish(session_id: str) -> dict[str, Any]:
    _enabled()
    return await service.publish(session_id)
