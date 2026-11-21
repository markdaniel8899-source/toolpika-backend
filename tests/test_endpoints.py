"""FastAPI endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.endpoints import admin, pipeline, tools
from app.main import app
from app.pipelines.orchestrator import PipelineResult
from app.pipelines.translator import TranslationResult

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert "groq" in response.json()["checks"]


def test_config_endpoint():
    response = client.get("/api/admin/config")
    assert response.status_code == 200
    assert "available_locales" in response.json()


def test_pipeline_trigger(monkeypatch):
    async def fake(slug=None):
        return PipelineResult(success=True, slug="word-counter", stage="complete", logs=["done"])

    monkeypatch.setattr(pipeline, "run_full_pipeline", fake)
    response = client.post("/api/pipeline/research-and-build", json={"topic": "word counter"})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_translate_endpoint(monkeypatch):
    async def fake(slug, locales=None):
        return TranslationResult(slug=slug, translated_locales=locales or ["de"])

    monkeypatch.setattr(pipeline, "translate_tool", fake)
    response = client.post("/api/pipeline/translate", json={"slug": "word-counter", "locales": ["de"]})
    assert response.json()["translated_locales"] == ["de"]


def test_list_tools(monkeypatch):
    monkeypatch.setattr(tools.publisher, "list_tools", lambda: [{"slug": "word-counter"}])
    response = client.get("/api/tools")
    assert response.status_code == 200
    assert response.json()[0]["slug"] == "word-counter"


def test_get_tool_not_found(monkeypatch):
    monkeypatch.setattr(tools.publisher, "get_tool", lambda slug: None)
    response = client.get("/api/tools/missing")
    assert response.status_code == 404


def test_retry_qa(monkeypatch, spec):
    monkeypatch.setattr(tools.publisher, "get_tool", lambda slug: {"spec": spec})
    response = client.post("/api/tools/word-counter/retry-qa")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_republish(monkeypatch, spec):
    monkeypatch.setattr(tools.publisher, "get_tool", lambda slug: {"spec": spec})
    monkeypatch.setattr(tools.publisher, "publish_spec", lambda s, h: s)
    response = client.post("/api/tools/word-counter/republish")
    assert response.json()["success"] is True


def test_pipeline_status(monkeypatch):
    monkeypatch.setattr(admin.supabase_client, "select", lambda *a: [])
    response = client.get("/api/admin/pipeline-status")
    assert response.status_code == 200
    assert "queue_depth" in response.json()


def test_admin_logs(monkeypatch):
    monkeypatch.setattr(admin.supabase_client, "select", lambda *a: [])
    response = client.get("/api/admin/logs?stage=qa")
    assert response.json() == []


def test_trigger_cron(monkeypatch):
    async def fake():
        return None

    monkeypatch.setattr(admin.cron_scheduler, "research_and_build", fake)
    response = client.post("/api/admin/trigger-cron")
    assert response.json()["success"] is True


def test_validation_error_response():
    response = client.post("/api/pipeline/translate", json={})
    assert response.status_code == 422
