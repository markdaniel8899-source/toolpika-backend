"""Hard-rule validator enforcing UNIVERSAL_TOOL_TEMPLATE.md."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.qa.example_tester import check_examples, prose_strings
from app.qa.rules import (
    BANNED_STRINGS,
    PLACEHOLDERS,
    all_strings,
    starts_with_same_two_words,
    unique_ratio,
    word_count,
)
from app.templates.tool_template import ToolSpec, ValidationResult


def validate_spec(
    spec: dict[str, Any],
    other_specs: list[dict[str, Any]] | None = None,
    registry: list[str] | None = None,
) -> ValidationResult:
    """Validate a ToolSpec dictionary and return structured errors/warnings.

    Args:
        spec: The generated tool specification.
        other_specs: Existing published specs used for FAQ uniqueness checks.
        registry: Known tool slugs used for relatedTools verification.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        ToolSpec.from_dict(spec)
    except ValidationError as exc:
        for issue in exc.errors():
            location = ".".join(str(part) for part in issue.get("loc", ()))
            errors.append(f"schema.{location}: {issue.get('msg', 'invalid')}")

    texts = all_strings(spec)
    lowered = [text.lower() for text in texts]

    for banned in BANNED_STRINGS:
        if any(banned in text for text in lowered):
            errors.append(f"banned string: {banned!r}")
    for placeholder in PLACEHOLDERS:
        if any(placeholder in text for text in texts):
            errors.append(f"unfilled placeholder: {placeholder!r}")

    direct_answer = str(spec.get("directAnswer", ""))
    answer_words = word_count(direct_answer)
    if not 40 <= answer_words <= 43:
        errors.append(
            f"directAnswer must be exactly 40-43 words (got {answer_words})"
        )

    h1 = str(spec.get("h1", ""))
    h1_words = word_count(h1)
    if h1_words > 6:
        errors.append(f"h1 must be max 6 words (got {h1_words})")
    keyword = str(spec.get("primaryKeyword", "")).strip().lower()
    if keyword and keyword not in h1.lower():
        errors.append("h1 must contain the primary keyword")

    seo = spec.get("seo") or {}
    title = str(seo.get("title", "")) if isinstance(seo, dict) else ""
    description = (
        str(seo.get("description", "")) if isinstance(seo, dict) else ""
    )
    if not 50 <= len(title) <= 60:
        errors.append(f"seo.title must be 50-60 characters (got {len(title)})")
    if not 120 <= len(description) <= 155:
        errors.append(
            f"seo.description must be 120-155 characters (got {len(description)})"
        )

    category = str(spec.get("category", "")).strip().lower()
    if category:
        for prose in prose_strings(spec):
            if category in prose.lower():
                errors.append("category name must not appear inside prose bodies")
                break

    tier = spec.get("tier", 1)
    if tier == 1:
        about = spec.get("about") or {}
        if not isinstance(about, dict):
            errors.append("about must be an object")
            about = {}
        if word_count(str(about.get("whatIs", ""))) < 200:
            errors.append("Tier 1: about.whatIs must be at least 200 words")
        if len(about.get("useCases") or []) < 3:
            errors.append("Tier 1: at least 3 use cases are required")
        if len(about.get("commonMistakes") or []) < 2:
            errors.append("Tier 1: at least 2 common mistakes are required")

    faqs = spec.get("faqs") or []
    if len(faqs) < 4 or len(faqs) > 8:
        errors.append("faqs must contain between 4 and 8 items")
    if tier == 1 and len(faqs) < 4:
        errors.append("Tier 1: at least 4 FAQs are required")

    if other_specs:
        questions = [
            str(faq.get("question", ""))
            for faq in faqs
            if isinstance(faq, dict)
        ]
        existing = [
            str(faq.get("question", ""))
            for other in other_specs
            for faq in (other.get("faqs") or [])
            if isinstance(faq, dict)
        ]
        ratio = unique_ratio(questions, existing)
        if ratio < 0.75:
            errors.append("FAQ uniqueness must be at least 75% across all tools")

    if registry is not None:
        for slug in spec.get("relatedTools") or []:
            if slug not in registry:
                errors.append(f"relatedTools slug not in registry: {slug}")

    errors.extend(check_examples(spec))

    # Warnings do not block publication.
    if keyword and keyword not in title.lower():
        warnings.append("primary keyword missing from seo.title")
    if keyword and keyword not in direct_answer.lower():
        warnings.append("primary keyword missing from directAnswer")
    questions = [
        str(faq.get("question", ""))
        for faq in faqs
        if isinstance(faq, dict)
    ]
    if starts_with_same_two_words(questions):
        warnings.append("more than 3 FAQs start with the same two words")
    blob = " ".join(texts).lower()
    if "/guides/" not in blob and "/blog/" not in blob:
        warnings.append("no internal link to a blog post")
    sentences = [part for part in direct_answer.split(".") if part.strip()]
    if sentences:
        average = answer_words / len(sentences)
        if average > 22:
            warnings.append("reading level may be too complex")

    return ValidationResult(
        isValid=not errors, errors=errors, warnings=warnings
    )
