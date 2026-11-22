"""API smoke tests for the new research-only backend."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.endpoints import admin, pipeline
from app.main import app
from app.pipelines.research_scout import ResearchResult

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_has_research_providers():
    response = client.get("/ready")
    assert response.status_code == 200
    checks = response.json()["checks"]
    assert "tavily" in checks and "nemotron" in checks
    assert "groq" not in checks


async def fake_scout():
    return ResearchResult(
        ideas=[
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "tool_name": "Word Counter",
                "category": "text",
                "why_trending": "Mentioned 15 times",
                "short_description": "Counts words locally.",
                "estimated_difficulty": "Easy",
                "status": "new",
            }
        ],
        sources_count=8,
        queries_run=4,
    )


def test_research_endpoint(monkeypatch):
    monkeypatch.setattr(pipeline, "run_research_scout", fake_scout)
    response = client.post("/api/pipeline/research")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["ideas"][0]["tool_name"] == "Word Counter"
    assert body["sources_count"] == 8


def test_list_ideas_returns_200_newest_first(monkeypatch):
    rows = [
        {
            "id": "a",
            "tool_name": "Older",
            "category": "text",
            "why_trending": "signal",
            "short_description": "desc",
            "estimated_difficulty": "Hard",
            "status": "new",
            "created_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": "b",
            "tool_name": "Newer",
            "category": "code",
            "why_trending": "signal",
            "short_description": "desc",
            "estimated_difficulty": "Easy",
            "status": "reviewed",
            "created_at": "2026-02-01T00:00:00Z",
        },
    ]
    monkeypatch.setattr(admin.supabase_client, "select", lambda *args: rows)
    response = client.get("/api/admin/ideas")
    assert response.status_code == 200, response.text
    assert [item["tool_name"] for item in response.json()] == ["Newer", "Older"]


def test_update_idea_status(monkeypatch):
    updated = {
        "id": "a",
        "tool_name": "Idea",
        "category": "text",
        "why_trending": "signal",
        "short_description": "desc",
        "estimated_difficulty": "Medium",
        "status": "rejected",
    }
    monkeypatch.setattr(admin.supabase_client, "update", lambda *args: [updated])
    response = client.patch("/api/admin/ideas/a", json={"status": "rejected"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


def test_update_idea_not_found(monkeypatch):
    monkeypatch.setattr(admin.supabase_client, "update", lambda *args: [])
    response = client.patch("/api/admin/ideas/missing", json={"status": "reviewed"})
    assert response.status_code == 404


def test_invalid_status_is_rejected():
    response = client.patch("/api/admin/ideas/a", json={"status": "unknown"})
    assert response.status_code == 422
