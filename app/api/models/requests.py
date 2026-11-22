"""Pydantic request models for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Optional topic for a targeted pipeline run."""

    topic: str | None = Field(default=None, max_length=200)


class TranslateRequest(BaseModel):
    """Translation trigger payload."""

    slug: str = Field(min_length=1, max_length=200)
    locales: list[str] | None = None


class LogFilter(BaseModel):
    """Filters for the admin log endpoint."""

    stage: str | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class StudioSessionRequest(BaseModel):
    """Create a Tool Studio chat session."""

    title: str | None = Field(default=None, max_length=120)
    idea: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)


class StudioChatRequest(BaseModel):
    """One chat turn in Tool Studio."""

    message: str = Field(min_length=1, max_length=8000)
    auto_plan: bool = True


class StudioPlanRequest(BaseModel):
    """Explicit research-and-plan request."""

    idea: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)


class StudioTranslateRequest(BaseModel):
    """Translation target locales for the current draft."""

    locales: list[str] | None = None
