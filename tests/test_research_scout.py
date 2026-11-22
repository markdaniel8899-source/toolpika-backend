"""Research scout tests - search, proposal and persistence only."""

from __future__ import annotations

import json
from typing import Any

from app.pipelines import research_scout
from app.pipelines.research_scout import ResearchScoutError


class FakeResponse:
    """Minimal httpx response double."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


def test_search_tavily_normalises_results(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["payload"] = kwargs["json"]
        return FakeResponse(
            {
                "results": [
                    {
                        "title": "Reddit thread",
                        "url": "https://reddit.com/r/webdev/1",
                        "content": "I wish there was a tool for X",
                    },
                    {"title": "No url", "content": "ignored"},
                ]
            }
        )

    monkeypatch.setattr(research_scout.httpx, "post", fake_post)
    monkeypatch.setattr(research_scout.settings, "tavily_api_key", "tvly-test")
    results = research_scout.search_tavily("need a tool")
    assert seen["url"] == "https://api.tavily.com/search"
    assert seen["payload"]["api_key"] == "tvly-test"
    assert len(results) == 2
    assert results[0]["query"] == "need a tool"


def test_collect_sources_deduplicates(monkeypatch):
    def fake_search(query, _counter=[0]):
        _counter[0] += 1
        url = f"https://example.com/{_counter[0]}"
        return [
            {"url": url, "title": "A", "content": "x", "query": query},
            {"url": url, "title": "A dup", "content": "x", "query": query},
        ]

    monkeypatch.setattr(research_scout, "search_tavily", fake_search)
    sources = research_scout.collect_sources()
    assert len(sources) == len(research_scout.SEARCH_QUERIES)
    assert len({item["url"] for item in sources}) == len(research_scout.SEARCH_QUERIES)


def test_propose_ideas_parses_fenced_json(monkeypatch):
    monkeypatch.setattr(research_scout.settings, "nvidia_nim_api_key", "nvapi-test")
    ideas_payload = [
        {
            "tool_name": "Syllable Counter",
            "category": "text",
            "why_trending": "Asked 15 times on r/webdev this month",
            "short_description": "Count syllables in a sentence instantly.",
            "estimated_difficulty": "easy",
        },
        {
            "tool_name": "Hex to RGB",
            "category": "unknown-category",
            "why_trending": "Repeated Product Hunt requests",
            "short_description": "Convert hex colours to RGB locally.",
            "estimated_difficulty": "Very Hard",
        },
        {
            "tool_name": "Incomplete",
            "why_trending": "",
            "short_description": "missing fields",
        },
    ]
    content = "```json\n" + json.dumps(ideas_payload) + "\n```"
    monkeypatch.setattr(
        research_scout.httpx,
        "post",
        lambda *_a, **_k: FakeResponse(
            {"choices": [{"message": {"content": content}}]}
        ),
    )

    ideas = research_scout.propose_ideas([{"url": "https://example.com", "content": "x"}])
    assert len(ideas) == 2
    assert ideas[0]["estimated_difficulty"] == "Easy"
    assert ideas[1]["category"] == "text"
    assert ideas[1]["estimated_difficulty"] == "Medium"


def test_propose_ideas_rejects_empty_output(monkeypatch):
    monkeypatch.setattr(research_scout.settings, "nvidia_nim_api_key", "nvapi-test")
    monkeypatch.setattr(
        research_scout.httpx,
        "post",
        lambda *_a, **_k: FakeResponse(
            {"choices": [{"message": {"content": "no json here"}}]}
        ),
    )
    try:
        research_scout.propose_ideas([{"url": "https://example.com"}])
    except ResearchScoutError as exc:
        assert "JSON array" in str(exc)
    else:
        raise AssertionError("expected ResearchScoutError")


async def test_run_research_scout_saves_ideas(monkeypatch):
    idea = {
        "tool_name": "Percent Calculator",
        "category": "calculator",
        "why_trending": "10 Quora questions",
        "short_description": "Calculate percentages locally.",
        "estimated_difficulty": "Easy",
    }
    monkeypatch.setattr(research_scout, "collect_sources", lambda: [{"url": "u"}])
    monkeypatch.setattr(research_scout, "propose_ideas", lambda sources: [idea])
    saved: list[dict[str, Any]] = []

    def fake_upsert(table, rows, conflict):
        saved.extend(rows)
        return rows

    monkeypatch.setattr(research_scout.supabase_client, "upsert", fake_upsert)
    result = await research_scout.run_research_scout()

    assert result.sources_count == 1
    assert len(result.ideas) == 1
    assert saved[0]["status"] == "new"
    assert saved[0]["tool_name"] == "Percent Calculator"
