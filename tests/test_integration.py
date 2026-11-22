"""Full pipeline integration tests with all external services mocked."""

from __future__ import annotations

import asyncio

from app.pipelines import orchestrator
from app.pipelines.research import ResearchResult
from tests.conftest import make_spec


def test_full_pipeline_success(monkeypatch, research):
    spec = make_spec()
    monkeypatch.setattr(orchestrator, "correct_spec", lambda s, e: s)
    monkeypatch.setattr(
        orchestrator.research,
        "research_trending_tools",
        lambda topic: asyncio.sleep(0, result=[research]) if False else _async_results([research]),
    )
    monkeypatch.setattr(orchestrator.generator, "generate_tool_spec", lambda r: spec)
    monkeypatch.setattr(orchestrator, "_known_slugs", lambda: [])
    monkeypatch.setattr(orchestrator.supabase_client, "select", lambda *a: [])
    published = []
    monkeypatch.setattr(
        orchestrator.publisher, "publish_spec", lambda s, h: published.append((s, h)) or s
    )
    scheduled = []
    monkeypatch.setattr(
        "app.services.queue.schedule_after",
        lambda minutes, job_id, func, *args: scheduled.append((minutes, job_id)),
    )
    monkeypatch.setattr(orchestrator, "_log_run", lambda *a, **k: None)

    result = asyncio.run(orchestrator.run_full_pipeline("word-counter"))
    assert result.success is True
    assert result.stage == "complete"
    assert len(published) == 1
    assert len(scheduled) == 1
    assert published[0][1] == orchestrator.source_hash(spec)


def test_full_pipeline_qa_failure_marks_status(monkeypatch, research):
    spec = make_spec()
    spec["directAnswer"] = "too short"
    monkeypatch.setattr(
        orchestrator.research,
        "research_trending_tools",
        lambda topic: _async_results([research]),
    )
    monkeypatch.setattr(orchestrator.generator, "generate_tool_spec", lambda r: spec)
    monkeypatch.setattr(orchestrator, "_known_slugs", lambda: [])
    monkeypatch.setattr(orchestrator.supabase_client, "select", lambda *a: [])
    monkeypatch.setattr(orchestrator, "correct_spec", lambda s, e: s)
    statuses = []
    monkeypatch.setattr(
        orchestrator.publisher,
        "mark_status",
        lambda slug, status, spec=None: statuses.append((slug, status)),
    )
    monkeypatch.setattr(orchestrator, "_log_run", lambda *a, **k: None)

    result = asyncio.run(orchestrator.run_full_pipeline("word-counter"))
    assert result.success is False
    assert result.stage == "qa_failed"
    assert statuses == [("word-counter", "qa_failed")]


def test_source_hash_is_stable(spec):
    assert orchestrator.source_hash(spec) == orchestrator.source_hash(spec)


async def _async_results(items):
    return items
