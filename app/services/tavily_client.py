"""Tavily search wrapper for autonomous tool research."""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


def search(query: str, search_depth: str = "advanced", max_results: int = 8) -> list[dict[str, Any]]:
    """Run one Tavily search and return normalised results."""
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")
    try:
        from tavily import TavilyClient
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("tavily-python package is not installed") from exc
    try:
        response = TavilyClient(api_key=settings.tavily_api_key).search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
        )
        return list(response.get("results") or [])
    except Exception as exc:
        log.error("tavily_search_failed", query=query, error=str(exc))
        raise
