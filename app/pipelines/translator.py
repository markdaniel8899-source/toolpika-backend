"""Chunked, rate-limit aware Groq translation for published tool specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config import settings
from app.qa.rules import KEEP_TERMS
from app.services import groq_client, supabase_client

log = structlog.get_logger(__name__)

CHUNKS = ("seo", "core", "deep", "faqs")


@dataclass
class TranslationResult:
    """Outcome of one translation run."""

    slug: str
    translated_locales: list[str] = field(default_factory=list)
    failed_locales: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_chunks(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Split a ToolSpec into the four translation chunks."""
    about = spec.get("about") or {}
    return {
        "seo": {
            "title": (spec.get("seo") or {}).get("title", ""),
            "description": (spec.get("seo") or {}).get("description", ""),
        },
        "core": {
            "h1": spec.get("h1", ""),
            "directAnswer": spec.get("directAnswer", ""),
            "features": spec.get("features") or [],
            "howToUse": spec.get("howToUse") or [],
        },
        "deep": {
            "whatIs": about.get("whatIs", ""),
            "useCases": about.get("useCases") or [],
            "commonMistakes": about.get("commonMistakes") or [],
            "limits": about.get("limits") or [],
        },
        "faqs": {"faqs": spec.get("faqs") or []},
    }


def build_prompt(locale: str, chunk_name: str) -> str:
    """Build a translation prompt that protects SEO limits and glossary terms."""
    keep = ", ".join(KEEP_TERMS)
    seo_rule = (
        "SEO title must stay within 60 characters, meta description within 155."
        if chunk_name == "seo"
        else ""
    )
    return (
        f"You translate website content from English to {locale}.\n"
        "Rules:\n"
        "- Keep meaning exact; do not add or remove facts.\n"
        f"- Keep these terms unchanged: {keep}\n"
        "- Do not translate code, inline `code`, URLs, or text inside code blocks.\n"
        "- Keep Markdown formatting.\n"
        "- Keep the tone simple and practical.\n"
        f"- {seo_rule}\n"
        "- Output valid JSON with the same keys as input."
    )


async def translate_tool(
    slug: str,
    target_locales: list[str] | None = None,
    spec: dict[str, Any] | None = None,
) -> TranslationResult:
    """Translate one tool into every target locale, chunk by chunk."""
    locales = target_locales or settings.locales
    result = TranslationResult(slug=slug)

    if spec is None:
        rows = supabase_client.select(
            "tool_specs", "slug,spec"
        )
        match = next((row for row in rows if row.get("slug") == slug), None)
        if not match:
            result.errors.append(f"tool spec not found: {slug}")
            result.failed_locales = list(locales)
            return result
        spec = match.get("spec") or {}

    chunks = build_chunks(spec)
    rows_to_save: list[dict[str, Any]] = []

    for locale in locales:
        try:
            for chunk_name in CHUNKS:
                translated = await groq_client.translate_json(
                    build_prompt(locale, chunk_name), chunks[chunk_name]
                )
                rows_to_save.append(
                    {
                        "locale": locale,
                        "slug": slug,
                        "chunk": chunk_name,
                        "content": translated,
                        "status": "published",
                    }
                )
                await groq_client.polite_delay()
            result.translated_locales.append(locale)
            log.info("locale_translated", slug=slug, locale=locale)
        except Exception as exc:  # noqa: BLE001 - one locale must not kill the run
            result.failed_locales.append(locale)
            result.errors.append(f"{locale}: {exc}")
            log.error("locale_translation_failed", slug=slug, locale=locale, error=str(exc))

    if rows_to_save:
        try:
            supabase_client.upsert(
                "content_translations", rows_to_save, "locale,slug,chunk"
            )
        except Exception as exc:
            result.errors.append(f"persistence: {exc}")

    if not result.failed_locales:
        try:
            supabase_client.upsert(
                "tool_specs",
                [{"slug": slug, "translation_status": "published"}],
                "slug",
            )
        except Exception as exc:
            result.errors.append(f"status update: {exc}")
    return result
