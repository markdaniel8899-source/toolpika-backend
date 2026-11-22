"""Research-scout trigger endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.models.requests import ResearchRequest
from app.api.models.responses import ResearchResponse
from app.pipelines.research_scout import ResearchScoutError, run_research_scout

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/research", response_model=ResearchResponse)
async def research(payload: ResearchRequest | None = None) -> ResearchResponse:
    """Scout the web and store fresh tool ideas for admin review."""
    try:
        result = await run_research_scout(payload.topic if payload else None)
    except ResearchScoutError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResearchResponse(
        success=True,
        ideas=result.ideas,
        sources_count=result.sources_count,
        queries_run=result.queries_run,
        topic=result.topic,
    )
