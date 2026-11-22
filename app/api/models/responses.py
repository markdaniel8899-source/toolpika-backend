"""Pydantic response models for the public API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str
    version: str
    uptime: float


class ReadyResponse(BaseModel):
    """Readiness response with provider checks."""

    ready: bool
    checks: dict[str, bool]


class ToolIdea(BaseModel):
    """One AI-scouted tool idea waiting for review."""

    id: str
    tool_name: str
    category: str
    why_trending: str
    short_description: str
    estimated_difficulty: str = "Medium"
    search_volume: str = "N/A"
    competition: str = "N/A"
    report_details: dict[str, Any] = Field(default_factory=dict)
    status: str = "new"
    created_at: str | None = None


class ResearchResponse(BaseModel):
    """Result of a manual scout run."""

    success: bool
    ideas: list[ToolIdea] = Field(default_factory=list)
    sources_count: int = 0
    queries_run: int = 0
    topic: str | None = None
    detail: str = ""

    model_config = {"extra": "ignore"}


class ChatResponse(BaseModel):
    """Result of one strategist chat turn."""

    reply: str
    action: str = "chat"
    topic: str | None = None
    ideas: list[ToolIdea] = Field(default_factory=list)
    research: dict[str, Any] = Field(default_factory=dict)
    context_tool_count: int = 0

    model_config = {"extra": "ignore"}


def as_idea(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a Supabase row for the ToolIdea response model."""
    return {key: value for key, value in row.items() if key in ToolIdea.model_fields}
