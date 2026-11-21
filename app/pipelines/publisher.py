"""Supabase publishing helpers for tool specs."""

from __future__ import annotations

from typing import Any

import structlog

from app.services import supabase_client

log = structlog.get_logger(__name__)


def publish_spec(spec: dict[str, Any], source_hash: str) -> dict[str, Any]:
    """Idempotently publish a validated spec to the tool_specs table."""
    row = {
        "slug": spec.get("slug"),
        "spec": spec,
        "status": "published",
        "translation_status": "pending",
        "source_hash": source_hash,
        "tier": spec.get("tier", 1),
        "category": spec.get("category"),
    }
    saved = supabase_client.upsert("tool_specs", [row], "slug")
    log.info("spec_published", slug=row["slug"], source_hash=source_hash)
    return saved[0] if saved else row


def list_tools() -> list[dict[str, Any]]:
    """Return every published tool spec."""
    return supabase_client.select(
        "tool_specs",
        "slug,status,tier,category,translation_status,source_hash,updated_at",
    )


def get_tool(slug: str) -> dict[str, Any] | None:
    """Return one tool spec by slug, or None."""
    rows = supabase_client.select("tool_specs", "slug,spec,translation_status,updated_at")
    return next((row for row in rows if row.get("slug") == slug), None)


def mark_status(slug: str, status: str) -> None:
    """Update the QA status of a tool."""
    supabase_client.upsert("tool_specs", [{"slug": slug, "status": status}], "slug")
