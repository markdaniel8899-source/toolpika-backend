"""ToolSpec generation via Nemotron 3.5 Super VL."""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings
from app.pipelines.research import ResearchResult
from app.services import nemotron_client
from app.templates.tool_template import load_template_markdown

log = structlog.get_logger(__name__)

RULES = """
You are writing an English tool-spec following UNIVERSAL_TOOL_TEMPLATE.md.
Output ONLY valid JSON. No markdown wrappers.
Every section must contain knowledge specific to this tool's topic.
Never insert the category name into sentences.
directAnswer is exactly 40-43 words.
FAQs come from People Also Ask, with at most one generic privacy FAQ.
Examples must be real and correct.
h1 is at most 6 words and contains the primary keyword.
seo.title is 50-60 characters; seo.description is 120-155 characters.
Tier 1 about.whatIs is at least 200 words, with 3+ use cases, 2+ common mistakes.
Return 4-8 FAQs and 3-6 relatedTools slugs.
"""

REQUIRED_TOP_KEYS = (
    "slug",
    "category",
    "name",
    "seo",
    "h1",
    "directAnswer",
    "about",
    "faqs",
)


def build_system_prompt() -> str:
    """Combine the canonical template with the hard generation rules."""
    return f"{load_template_markdown()}\n\n{RULES}"


def build_user_prompt(research: ResearchResult) -> str:
    """Build the generation prompt for one research candidate."""
    return (
        f"Topic: {research.topic}\n"
        f"Demand signal: {research.demand_signal}\n"
        f"User quotes: {research.quotes}\n"
        f"Competitor gaps: {research.competitor_gaps}\n\n"
        "Produce a complete ToolSpec JSON now."
    )


def generate_tool_spec(research: ResearchResult) -> dict[str, Any]:
    """Generate a raw ToolSpec dictionary, retrying malformed model output."""
    system_prompt = build_system_prompt()
    last_error: Exception | None = None
    for attempt in range(1, settings.qa_max_retries + 1):
        try:
            payload = nemotron_client.generate_json(
                system_prompt, build_user_prompt(research)
            )
            missing = [key for key in REQUIRED_TOP_KEYS if key not in payload]
            if missing:
                raise ValueError(f"missing keys: {', '.join(missing)}")
            log.info("generation_succeeded", topic=research.topic, attempt=attempt)
            return payload
        except Exception as exc:  # noqa: BLE001 - generator must retry any failure
            last_error = exc
            log.warning("generation_attempt_failed", attempt=attempt, error=str(exc))
    raise RuntimeError(f"generation failed after {settings.qa_max_retries} attempts: {last_error}")
