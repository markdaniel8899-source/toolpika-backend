"""Strategy engine tests: RAG context, intent routing and chat endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.endpoints import admin
from app.main import app
from app.pipelines import chat_engine, research_scout
from app.pipelines.chat_engine import ChatResult, handle_chat
from app.services import context_builder, supabase_client

client = TestClient(app)


def test_context_builder_uses_supabase_tools(monkeypatch):
    rows = [
        {"slug": "word-counter", "title": "Word Counter", "status": "live"},
        {"slug": "hidden-tool", "title": "Hidden", "status": "hidden"},
        {"slug": "json-formatter", "title": "JSON Formatter", "status": "published"},
    ]
    monkeypatch.setattr(supabase_client, "select", lambda *args: rows)
    context = context_builder.get_existing_tools_context()
    assert "Word Counter (slug: word-counter)" in context
    assert "JSON Formatter (slug: json-formatter)" in context
    assert "Hidden" not in context
    assert "2 total" in context


def test_context_builder_falls_back_when_db_fails(monkeypatch):
    def boom(*_args):
        raise RuntimeError("offline")

    monkeypatch.setattr(supabase_client, "select", boom)
    context = context_builder.get_existing_tools_context()
    assert "word-counter" in context
    assert len(context_builder.get_existing_tools()) == 8


def test_system_prompt_contains_live_context():
    prompt = chat_engine.build_system_prompt("- Word Counter (slug: word-counter)")
    assert "AI Strategist" in prompt
    assert "word-counter" in prompt
    assert "run_research" in prompt
    assert "Never suggest building a tool that already exists" in prompt


async def test_chat_mode_replies_conversationally(monkeypatch):
    monkeypatch.setattr(
        chat_engine, "get_existing_tools_context", lambda: "- Word Counter (slug: word-counter)"
    )
    monkeypatch.setattr(chat_engine, "_call_model", lambda messages: "A handy idea, but check duplicates.")

    result = await handle_chat("What do you think about a word counter?", "chat")
    assert result.action == "chat"
    assert result.context_tool_count == 1
    assert "duplicates" in result.reply


async def test_research_command_triggers_pipeline(monkeypatch):
    monkeypatch.setattr(
        chat_engine, "get_existing_tools_context", lambda: "- Word Counter (slug: word-counter)"
    )
    monkeypatch.setattr(
        chat_engine,
        "_call_model",
        lambda messages: '```json\n{"action": "run_research", "topic": "CSV tools"}\n```',
    )

    captured: dict[str, object] = {}

    async def fake_scout(topic=None):
        captured["topic"] = topic
        return research_scout.ResearchResult(
            ideas=[
                {
                    "id": "1",
                    "tool_name": "CSV Splitter",
                    "category": "text",
                    "why_trending": "20 Reddit mentions",
                    "short_description": "Split CSV rows locally.",
                    "estimated_difficulty": "Easy",
                    "search_volume": "High",
                    "competition": "Medium",
                    "report_details": {"target_audience": "Analysts"},
                }
            ],
            sources_count=12,
            queries_run=4,
            topic=topic,
        )

    monkeypatch.setattr(chat_engine, "run_research_scout", fake_scout)
    result = await handle_chat("research CSV tools")
    assert captured["topic"] == "CSV tools"
    assert result.action == "run_research"
    assert result.ideas[0]["tool_name"] == "CSV Splitter"
    assert result.research["sources_count"] == 12


def test_chat_endpoint(monkeypatch):
    async def fake_handle(message, mode=None, history=None):
        return ChatResult(
            reply="Research complete.",
            action="run_research",
            topic="trends",
            ideas=[
                {
                    "id": "1",
                    "tool_name": "Idea",
                    "category": "text",
                    "why_trending": "signal",
                    "short_description": "desc",
                }
            ],
            research={"sources_count": 5},
            context_tool_count=8,
        )

    monkeypatch.setattr(admin, "handle_chat", fake_handle)
    response = client.post(
        "/api/admin/chat",
        json={"message": "find trending tools", "mode": "research", "history": []},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "run_research"
    assert body["ideas"][0]["tool_name"] == "Idea"
    assert body["context_tool_count"] == 8
