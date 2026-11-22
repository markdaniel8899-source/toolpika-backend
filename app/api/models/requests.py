"""Pydantic request models for the public API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class IdeaStatusUpdate(BaseModel):
    """Admin decision on a scouted tool idea."""

    status: Literal["new", "reviewed", "rejected", "building"]
