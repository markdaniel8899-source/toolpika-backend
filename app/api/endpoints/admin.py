"""Admin endpoints for reviewing scouted tool ideas."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.models.requests import IdeaStatusUpdate
from app.api.models.responses import ToolIdea, as_idea
from app.services import supabase_client

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/ideas", response_model=list[ToolIdea])
async def list_ideas() -> list[dict[str, Any]]:
    """Return all ideas, newest first."""
    try:
        rows = supabase_client.select("tool_ideas", "*")
    except Exception as exc:  # noqa: BLE001 - surface a clean API error
        raise HTTPException(status_code=502, detail=f"Could not load ideas: {exc}") from exc
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return [as_idea(row) for row in rows]


@router.patch("/ideas/{idea_id}", response_model=ToolIdea)
async def update_idea(idea_id: str, payload: IdeaStatusUpdate) -> dict[str, Any]:
    """Update the review status of one idea."""
    try:
        updated = supabase_client.update(
            "tool_ideas", {"status": payload.status}, {"id": idea_id}
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not update idea: {exc}") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Idea not found.")
    return as_idea(updated[0])
