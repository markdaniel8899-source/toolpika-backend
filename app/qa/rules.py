"""Static rule constants and small text helpers used by the QA layer."""

from __future__ import annotations

import re

CATEGORIES = {
    "text",
    "image",
    "file",
    "code",
    "converter",
    "calculator",
    "security",
}

BANNED_STRINGS = (
    "converters tool",
    "converters fix",
    "converters job",
    "converters action",
    "converters utility",
    "a free {category} tool that",
    "get out of the way",
)

PLACEHOLDERS = ("{", "}", "undefined", "null", "[object Object]")

KEEP_TERMS = (
    "Toolpika",
    "JavaScript",
    "Base64",
    "JSON",
    "URL",
    "UTF-8",
    "Canvas API",
    "File API",
)

CATEGORY_LABELS = {
    "text": "text",
    "image": "image",
    "file": "file",
    "code": "code",
    "converter": "converter",
    "calculator": "calculator",
    "security": "security",
}


def word_count(text: str) -> int:
    """Count whitespace-separated words in a string."""
    return len(re.findall(r"\S+", text or ""))


def starts_with_same_two_words(questions: list[str]) -> bool:
    """Return True when more than 3 questions share their first two words."""
    counts: dict[str, int] = {}
    for question in questions:
        key = " ".join((question or "").strip().lower().split()[:2])
        counts[key] = counts.get(key, 0) + 1
    return any(count > 3 for count in counts.values())


def unique_ratio(questions: list[str], existing: list[str]) -> float:
    """Fraction of questions absent from an existing corpus.

    When the corpus is empty all questions count as unique.
    """
    if not questions:
        return 0.0
    existing_lower = {item.strip().lower() for item in existing}
    fresh = sum(
        1
        for question in questions
        if question.strip().lower() not in existing_lower
    )
    return fresh / len(questions)


def all_strings(value: object) -> list[str]:
    """Recursively collect every string inside a JSON-like structure."""
    result: list[str] = []
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            result.extend(all_strings(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(all_strings(item))
    return result
