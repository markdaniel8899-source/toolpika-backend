"""Live site context for the Studio assistant (lightweight RAG).

The site inventory and published ToolSpecs are retrieved from Supabase on every
request, merged with the static frontend registry, and ranked lexically against
the admin's message. The top specs are injected into the model prompt, so the
assistant always knows which tools exist and what their pages say.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import structlog

from app.config import settings
from app.registry import seed_tools
from app.services import supabase_client

log = structlog.get_logger(__name__)

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "your",
    "you",
    "are",
    "was",
    "have",
    "has",
    "tool",
    "tools",
    "make",
    "build",
    "create",
    "want",
    "need",
    "please",
    "kya",
    "kar",
    "karo",
    "hai",
    "main",
    "mein",
}


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _load_spec_rows() -> list[dict[str, Any]]:
    """Load published specs, returning an empty list when Supabase is offline."""
    if (
        settings.is_test
        or not settings.supabase_url
        or not settings.supabase_service_role_key
    ):
        return []
    try:
        return supabase_client.select(
            "tool_specs", "slug,spec,category,status,translation_status"
        )
    except Exception as exc:  # noqa: BLE001 - context must never break chat
        log.warning("studio_context_lookup_failed", error=str(exc))
        return []


def _spec_name(spec: dict[str, Any], slug: str) -> str:
    return str(spec.get("name") or slug.replace("-", " ").title())


def inventory() -> list[dict[str, Any]]:
    """Return every tool the site knows about, with DB rows taking precedence."""
    tools: dict[str, dict[str, Any]] = {
        str(tool["slug"]): {
            "slug": str(tool["slug"]),
            "name": str(tool["name"]),
            "category": str(tool["category"]),
            "description": str(tool.get("description", "")),
            "status": "live",
            "translation_status": "published",
            "source": "frontend-registry",
        }
        for tool in seed_tools()
    }
    for row in _load_spec_rows():
        slug = str(row.get("slug") or "")
        if not slug:
            continue
        spec = row.get("spec") or {}
        tools[slug] = {
            "slug": slug,
            "name": _spec_name(spec, slug),
            "category": str(row.get("category") or spec.get("category") or "text"),
            "description": str(
                (spec.get("seo") or {}).get("description")
                or spec.get("directAnswer")
                or ""
            ),
            "status": str(row.get("status") or "published"),
            "translation_status": str(row.get("translation_status") or "pending"),
            "source": "supabase",
        }
    return sorted(tools.values(), key=lambda item: item["slug"])


def _compact_spec(slug: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Keep the parts of a ToolSpec that are useful in a model prompt."""
    about = spec.get("about") or {}
    faqs = spec.get("faqs") or []
    return {
        "slug": slug,
        "name": _spec_name(spec, slug),
        "category": spec.get("category"),
        "primaryKeyword": spec.get("primaryKeyword"),
        "seo": spec.get("seo"),
        "h1": spec.get("h1"),
        "directAnswer": spec.get("directAnswer"),
        "features": (spec.get("features") or [])[:7],
        "howToUse": (spec.get("howToUse") or [])[:6],
        "about": {
            "whatIs": str(about.get("whatIs", ""))[:1200],
            "useCases": (about.get("useCases") or [])[:5],
            "commonMistakes": (about.get("commonMistakes") or [])[:4],
        },
        "faqQuestions": [
            str(faq.get("question", ""))
            for faq in faqs
            if isinstance(faq, dict)
        ][:8],
        "relatedTools": (spec.get("relatedTools") or [])[:8],
    }


def _score(query_terms: set[str], spec: dict[str, Any], slug: str) -> float:
    haystack = " ".join(
        [
            slug,
            str(spec.get("name", "")),
            str(spec.get("primaryKeyword", "")),
            str(spec.get("category", "")),
            str(spec.get("directAnswer", "")),
            " ".join(str(item) for item in spec.get("features") or []),
            " ".join(
                str(faq.get("question", ""))
                for faq in spec.get("faqs") or []
                if isinstance(faq, dict)
            ),
        ]
    ).lower()
    score = 0.0
    if slug.lower() in query_terms:
        score += 12.0
    for term in query_terms:
        if term in slug.lower():
            score += 6.0
        score += min(3.0, haystack.count(term))
    return score


def relevant_specs(
    query: str,
    tools: list[dict[str, Any]] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return the most relevant published specs for a query."""
    rows = _load_spec_rows()
    if not rows:
        # No published specs yet: give the model the seed inventory instead of
        # pretending the site is empty.
        return [
            {
                "slug": tool["slug"],
                "name": tool["name"],
                "category": tool["category"],
                "description": tool.get("description", ""),
                "source": "frontend-registry",
            }
            for tool in (tools or inventory())
        ][: (limit or settings.studio_context_specs)]

    terms = _terms(query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        slug = str(row.get("slug") or "")
        spec = row.get("spec") or {}
        if not slug or not spec:
            continue
        ranked.append((_score(terms, spec, slug), _compact_spec(slug, spec)))
    ranked.sort(key=lambda item: item[0], reverse=True)

    # Always include a few recent specs even when the query has no keywords, so
    # the assistant can answer "what does the site have?".
    selected = [item for item in ranked[: (limit or settings.studio_context_specs)]]
    return [item[1] for item in selected]


def build_context(query: str = "") -> dict[str, Any]:
    """Build the live RAG context injected into every Studio prompt."""
    tools = inventory()
    specs = relevant_specs(query, tools)
    return {
        "site": {
            "name": "Toolpika",
            "url": settings.frontend_url,
            "locales": settings.locales,
            "tool_count": len(tools),
            "tools": tools,
        },
        "relevant_specs": specs,
        "rules": [
            "Every tool runs entirely in the visitor's browser.",
            "Never claim a tool exists unless it is in site.tools.",
            "Generated tools must be client-side, privacy-first and accessible.",
            "Tool pages follow markdown/UNIVERSAL_TOOL_TEMPLATE.md.",
            "Content is translated into the configured locales with Groq.",
        ],
        "pipeline": {
            "generation_model": settings.nemotron_model,
            "translation_model": settings.groq_model,
            "qa_max_retries": settings.qa_max_retries,
            "translation_delay_minutes": settings.translation_delay_minutes,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def context_digest(context: dict[str, Any]) -> dict[str, Any]:
    """Small summary shown in the admin chat header."""
    site = context.get("site") or {}
    tools = site.get("tools") or []
    return {
        "tool_count": len(tools),
        "published_count": sum(
            1 for tool in tools if tool.get("status") == "published"
        ),
        "locales": site.get("locales") or [],
        "tools": [
            {"slug": str(tool.get("slug") or ""), "name": str(tool.get("name") or "")}
            for tool in tools[:30]
        ],
        "relevant_slugs": [
            str(spec.get("slug"))
            for spec in context.get("relevant_specs") or []
        ],
    }
