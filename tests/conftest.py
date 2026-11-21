"""Shared pytest fixtures. Sets test mode before any app module is imported."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("QA_MAX_RETRIES", "3")
os.environ.setdefault("TRANSLATION_CALL_DELAY_SECONDS", "0")

from typing import Any  # noqa: E402

import pytest  # noqa: E402

from app.pipelines.research import ResearchResult  # noqa: E402


def _words(count: int, token: str = "word") -> str:
    return " ".join([token] * count)


def make_spec() -> dict[str, Any]:
    """Build a fully valid Tier 1 ToolSpec for tests."""
    return {
        "slug": "word-counter",
        "category": "text",
        "tier": 1,
        "indexable": True,
        "name": "Word Counter",
        "shortName": "Word Counter",
        "componentId": "word-counter",
        "primaryKeyword": "word counter",
        "secondaryKeywords": ["word count", "count characters"],
        "searchIntent": "Count words and characters quickly",
        "peopleAlsoAsk": ["How many words do I have?", "Is it private?"],
        "seo": {
            "title": "Word Counter — Fast Free Private Tool For Everyone Today",
            "description": (
                "Count words, characters and sentences instantly in your browser. "
                "No upload, no account and no sign-up. Paste your draft and read "
                "the counts straight away."
            ),
        },
        "h1": "Word Counter Online",
        "directAnswer": _words(42),
        "howToUse": [
            "Paste your draft into the input box.",
            "Read the live counts on the right.",
            "Copy the result and start again.",
        ],
        "example": [{"input": "hello world", "output": "2"}],
        "features": ["Instant counts", "Runs locally", "No upload"],
        "about": {
            "whatIs": _words(210),
            "useCases": ["Students", "Writers", "Editors"],
            "commonMistakes": ["Forgetting punctuation", "Counting spaces"],
            "limits": ["Very large drafts may be slow"],
        },
        "faqs": [
            {"question": "Is it free?", "answer": "Yes, it is free to use."},
            {"question": "Does it upload?", "answer": "No, everything runs locally."},
            {"question": "Any install?", "answer": "No, it is a web page."},
            {"question": "Mobile support?", "answer": "Yes, it fits small screens."},
        ],
        "relatedTools": [],
        "trust": {"author": "Toolpika", "lastUpdated": "2026-11-21"},
        "schema": {
            "softwareApplication": True,
            "faqPage": True,
            "howTo": True,
            "breadcrumb": True,
        },
        "translation": {"keep": ["Toolpika"], "note": "Keep code unchanged"},
    }


@pytest.fixture
def spec() -> dict[str, Any]:
    """Return a fresh valid tool spec."""
    return make_spec()


@pytest.fixture
def research() -> ResearchResult:
    """Return a research result for generator tests."""
    return ResearchResult(
        topic="word counter",
        demand_signal="community discussion",
        quotes=["I wish there was a simple word counter"],
        competitor_gaps=["existing tools are slow"],
        score=2.5,
    )
