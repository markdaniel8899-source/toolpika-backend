"""Autonomous trending-tool research using Tavily."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.services import tavily_client

log = structlog.get_logger(__name__)

QUERIES = (
    '"need a tool for" OR "wish there was a calculator for" site:reddit.com OR site:quora.com',
    '"new tool" OR "launching" site:producthunt.com',
    '"online tool" OR "web app" trending 2026',
)


@dataclass
class ResearchResult:
    """One ranked tool idea with its demand signals."""

    topic: str
    demand_signal: str
    quotes: list[str]
    competitor_gaps: list[str]
    score: float
    context: dict[str, Any] = field(default_factory=dict)


def _topic_from_title(title: str) -> str:
    """Turn a search result title into a short tool topic phrase."""
    cleaned = title.split("|")[0].split("-")[0].strip()
    return cleaned[:80] or title[:80]


def _rank(results: list[dict[str, Any]]) -> list[ResearchResult]:
    """Rank raw Tavily results into distinct tool ideas."""
    candidates: dict[str, ResearchResult] = {}
    for item in results:
        title = str(item.get("title", ""))
        url = str(item.get("url", ""))
        if not title:
            continue
        topic = _topic_from_title(title)
        demand = "community discussion" if "reddit" in url or "quora" in url else "launch signal"
        gap = "existing tools are described as slow or complicated" if demand == "community discussion" else "new market entry"
        score = 2.0 if demand == "community discussion" else 1.0
        score += min(1.0, len(str(item.get("content", ""))) / 1000)
        existing = candidates.get(topic)
        if existing:
            existing.score += 0.5
            if item.get("content"):
                existing.quotes.append(str(item["content"])[:240])
        else:
            candidates[topic] = ResearchResult(
                topic=topic,
                demand_signal=demand,
                quotes=[str(item.get("content", ""))[:240]],
                competitor_gaps=[gap],
                score=score,
            )
    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)[:3]


async def research_trending_tools(topic: str | None = None) -> list[ResearchResult]:
    """Research trending tools, or build a focused result for a given topic."""
    if topic:
        results = await asyncio.to_thread(tavily_client.search, topic, "advanced", 6)
        ranked = _rank(results)
        if ranked:
            ranked[0].topic = topic
            return ranked[:1]
        return [
            ResearchResult(
                topic=topic,
                demand_signal="operator supplied topic",
                quotes=[],
                competitor_gaps=["manual request"],
                score=1.0,
            )
        ]

    batches = await asyncio.gather(
        *[
            asyncio.to_thread(tavily_client.search, query, "advanced", 8)
            for query in QUERIES
        ],
        return_exceptions=True,
    )
    merged: list[dict[str, Any]] = []
    for batch in batches:
        if isinstance(batch, Exception):
            log.warning("research_query_failed", error=str(batch))
            continue
        merged.extend(batch)
    ranked = _rank(merged)
    for result in ranked:
        result.context = {
            "source": "tavily",
            "queries": list(QUERIES),
            "topic": result.topic,
        }
    log.info("research_complete", candidates=len(ranked))
    return ranked
