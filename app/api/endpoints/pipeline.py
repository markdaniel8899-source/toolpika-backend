"""Pipeline trigger endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.models.requests import ResearchRequest, TranslateRequest
from app.api.models.responses import PipelineResponse, TranslationResponse
from app.pipelines.orchestrator import run_full_pipeline
from app.pipelines.translator import translate_tool

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/research-and-build", response_model=PipelineResponse)
async def research_and_build(payload: ResearchRequest) -> PipelineResponse:
    """Research, generate, QA, publish and schedule translation."""
    result = await run_full_pipeline(payload.topic)
    return PipelineResponse(
        success=result.success,
        slug=result.slug,
        stage=result.stage,
        logs=result.logs,
    )


@router.post("/translate", response_model=TranslationResponse)
async def translate(payload: TranslateRequest) -> TranslationResponse:
    """Run chunked translation for one tool."""
    result = await translate_tool(payload.slug, payload.locales)
    return TranslationResponse(
        success=not result.failed_locales and not result.errors,
        translated_locales=result.translated_locales,
        failed_locales=result.failed_locales,
    )
