"""Pydantic response models for the public API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineResponse(BaseModel):
    """Result of a pipeline trigger."""

    success: bool
    slug: str | None = None
    stage: str
    logs: list[str] = Field(default_factory=list)


class TranslationResponse(BaseModel):
    """Result of a translation trigger."""

    success: bool
    translated_locales: list[str] = Field(default_factory=list)
    failed_locales: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str
    version: str
    uptime: float


class ReadyResponse(BaseModel):
    """Readiness response with provider checks."""

    ready: bool
    checks: dict[str, bool]


class ConfigResponse(BaseModel):
    """Frontend-facing pipeline configuration."""

    pipeline_enabled: bool
    available_locales: list[str]
    max_retries: int


class GenericResponse(BaseModel):
    """Small generic success envelope."""

    success: bool
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
