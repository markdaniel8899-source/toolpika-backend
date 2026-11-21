"""Research pipeline tests with mocked Tavily."""

from __future__ import annotations

import asyncio

from app.pipelines import research


def test_queries_are_defined():
    assert len(research.QUERIES) == 3
    assert "reddit.com" in research.QUERIES[0]


def test_rank_returns_top_three():
    raw = [
        {"title": f"Need a tool for task {i}", "url": "https://reddit.com/r/x", "content": "long content" * 10}
        for i in range(5)
    ]
    ranked = research._rank(raw)
    assert len(ranked) == 3
    assert all(item.demand_signal == "community discussion" for item in ranked)


def test_topic_search_uses_topic(monkeypatch):
    seen = []

    def fake_search(query, depth, max_results):
        seen.append(query)
        return []

    monkeypatch.setattr(research.tavily_client, "search", fake_search)
    result = asyncio.run(research.research_trending_tools("invoice parser"))
    assert seen == ["invoice parser"]
    assert result[0].topic == "invoice parser"


def test_autonomous_research_merges_batches(monkeypatch):
    def fake_search(query, depth, max_results):
        return [
            {
                "title": "Need a tool for invoices",
                "url": "https://reddit.com/r/x",
                "content": "quotes",
            }
        ]

    monkeypatch.setattr(research.tavily_client, "search", fake_search)
    results = asyncio.run(research.research_trending_tools())
    assert len(results) == 1
    assert results[0].context["source"] == "tavily"


def test_research_result_dataclass(research):
    assert research.score > 0
    assert isinstance(research.quotes, list)
