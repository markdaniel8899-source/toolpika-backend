"""Pydantic request models for the public API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Optional topic focus for a manual scout run."""

    topic: str | None = Field(default=None, max_length=200)


class IdeaStatusUpdate(BaseModel):
    """Admin decision on a scouted tool idea."""

    status: Literal["new", "reviewed", "rejected", "building"]


class ChatMessage(BaseModel):
    """One prior turn sent by the admin UI for conversational context."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    """A strategist chat turn with optional mode override."""

    message: str = Field(min_length=1, max_length=4000)
    mode: Literal["chat", "research"] | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
