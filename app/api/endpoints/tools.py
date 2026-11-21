"""Tool spec CRUD and maintenance endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.models.responses import GenericResponse
from app.pipelines import publisher
from app.qa.validator import validate_spec

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools() -> list[dict[str, Any]]:
    """List all tools with publication and translation status."""
    return publisher.list_tools()


@router.get("/{slug}")
async def get_tool(slug: str) -> dict[str, Any]:
    """Return a full tool spec plus translation status."""
    tool = publisher.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/{slug}/retry-qa", response_model=GenericResponse)
async def retry_qa(slug: str) -> GenericResponse:
    """Re-run QA on an existing spec and report the result."""
    tool = publisher.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    result = validate_spec(tool.get("spec") or {})
    return GenericResponse(
        success=result.isValid,
        detail="qa passed" if result.isValid else "qa failed",
        data={"errors": result.errors, "warnings": result.warnings},
    )


@router.post("/{slug}/republish", response_model=GenericResponse)
async def republish(slug: str) -> GenericResponse:
    """Recompute the source hash and re-publish a tool spec."""
    from app.pipelines.orchestrator import source_hash

    tool = publisher.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    spec = tool.get("spec") or {}
    publisher.publish_spec(spec, source_hash(spec))
    return GenericResponse(success=True, detail="republished", data={"slug": slug})
