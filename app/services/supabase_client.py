"""Supabase client factory and table helpers."""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


def get_client() -> Any:
    """Create a Supabase client with the service-role key."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase credentials are not configured")
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("supabase package is not installed") from exc
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def upsert(table: str, rows: list[dict[str, Any]], on_conflict: str) -> list[dict[str, Any]]:
    """Idempotently insert rows into a Supabase table."""
    if not rows:
        return []
    try:
        response = (
            get_client().table(table).upsert(rows, on_conflict=on_conflict).execute()
        )
        return list(response.data or [])
    except Exception as exc:
        log.error("supabase_upsert_failed", table=table, error=str(exc))
        raise


def select(table: str, columns: str = "*") -> list[dict[str, Any]]:
    """Select rows from a Supabase table."""
    try:
        response = get_client().table(table).select(columns).execute()
        return list(response.data or [])
    except Exception as exc:
        log.error("supabase_select_failed", table=table, error=str(exc))
        raise
