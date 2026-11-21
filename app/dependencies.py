"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Any

from app.services import supabase_client


def get_supabase() -> Any:
    """Return a Supabase client for request-scoped use."""
    return supabase_client.get_client()
