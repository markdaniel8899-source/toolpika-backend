"""Context builder for the AI strategist (RAG over the live tool catalogue)."""

from __future__ import annotations

from typing import Any

import structlog

from app.services import supabase_client

log = structlog.get_logger(__name__)

LIVE_STATUSES = {"live", "published", "active"}

# Last-resort inventory mirroring frontend/src/lib/tools/registry.ts. Used only
# when Supabase is unreachable, so the strategist never claims the site is empty.
FALLBACK_TOOLS: tuple[tuple[str, str], ...] = (
    ("word-counter", "Word Counter"),
    ("case-converter", "Case Converter"),
    ("image-compressor", "Image Compressor"),
    ("json-formatter", "JSON Formatter"),
    ("unit-converter", "Unit Converter"),
    ("password-generator", "Password Generator"),
    ("url-encoder", "URL Encoder / Decoder"),
    ("base64-encoder", "Base64 Encoder / Decoder"),
)


def get_existing_tools() -> list[dict[str, str]]:
    """Return published tools from Supabase, with a static fallback."""
    try:
        rows = supabase_client.select("tools", "slug,title,status,category")
    except Exception as exc:  # noqa: BLE001 - chat must survive DB outages
        log.warning("context_builder_db_failed", error=str(exc))
        rows = []

    tools: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        slug = str(row.get("slug") or "").strip()
        status = str(row.get("status") or "live").strip().lower()
        if not slug or slug in seen or status not in LIVE_STATUSES:
            continue
        seen.add(slug)
        tools.append(
            {
                "slug": slug,
                "name": str(row.get("title") or slug.replace("-", " ").title()),
                "category": str(row.get("category") or ""),
            }
        )

    if not tools:
        tools = [
            {"slug": slug, "name": name, "category": ""}
            for slug, name in FALLBACK_TOOLS
        ]
    return tools


def get_existing_tools_context() -> str:
    """Format the live catalogue for injection into the system prompt."""
    tools: list[dict[str, Any]] = get_existing_tools()
    lines = [f"- {tool['name']} (slug: {tool['slug']})" for tool in tools]
    return (
        f"Published tools currently on Toolpika ({len(lines)} total):\n"
        + "\n".join(lines)
    )
