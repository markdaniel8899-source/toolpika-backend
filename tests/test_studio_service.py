"""Studio orchestration tests with all providers mocked."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.pipelines import translator
from app.studio import service
from app.templates.tool_template import ValidationResult
from tests.conftest import make_spec

BLUEPRINT = {
    "slug": "word-count",
    "name": "Word Count",
    "category": "text",
    "archetype": "text-analyzer",
    "description": "Count words in your text.",
    "input_label": "Text",
    "input_placeholder": "Paste text here",
    "run_label": "Count",
    "output_label": "Count",
    "features": ["Fast", "Local", "Private"],
    "examples": [{"input": "hello world", "output": "2"}],
    "related_tools": ["word-counter"],
    "icon": "Wand2",
}

CONTEXT = {
    "site": {
        "name": "Toolpika",
        "url": "https://toolpika.site",
        "locales": ["de", "fr"],
        "tool_count": 1,
        "tools": [{"slug": "word-counter", "name": "Word Counter", "status": "live"}],
    },
    "relevant_specs": [],
    "rules": [],
    "pipeline": {},
}


def _spec():
    spec = make_spec()
    spec["slug"] = BLUEPRINT["slug"]
    spec["name"] = BLUEPRINT["name"]
    spec["shortName"] = BLUEPRINT["name"]
    spec["componentId"] = BLUEPRINT["slug"]
    spec["primaryKeyword"] = "word count"
    spec["h1"] = "Word Count Online"
    return spec


def _install_mocks(monkeypatch, code_ok: bool = True) -> None:
    monkeypatch.setattr(service.context, "build_context", lambda query="": CONTEXT)
    monkeypatch.setattr(
        service.research,
        "research",
        lambda idea=None, url=None: {
            "idea": idea or "word count tool",
            "summary": "Count words quickly.",
            "features": ["Fast", "Local", "Private"],
            "suggested_name": "Word Count",
            "suggested_slug": "word-count",
            "competitors": [],
        },
    )
    monkeypatch.setattr(
        service.planner, "generate_blueprint", lambda research, context: dict(BLUEPRINT)
    )
    monkeypatch.setattr(
        service.planner,
        "generate_spec",
        lambda blueprint, research, context: (
            _spec(),
            ValidationResult(isValid=True, errors=[], warnings=[]),
        ),
    )
    monkeypatch.setattr(
        service.codegen,
        "generate_code",
        lambda blueprint, spec: {
            "ok": code_ok,
            "code": "export function run(input: string): string { return input; }",
            "errors": [],
            "warnings": [],
            "checks": {"signature": True},
            "attempts": 1,
            "notes": "",
        },
    )
    monkeypatch.setattr(service.codegen, "resolve_frontend_path", lambda: None)
    monkeypatch.setattr(
        service.codegen, "load_manifest", lambda root: {"version": 1, "tools": []}
    )
    monkeypatch.setattr(
        service.codegen,
        "apply_files",
        lambda files: {
            "applied": False,
            "reason": "no frontend on this server",
            "written": [],
        },
    )

    async def fake_translate(slug, locales=None, spec=None):
        return translator.TranslationResult(
            slug=slug, translated_locales=locales or ["de"]
        )

    monkeypatch.setattr(service.translator, "translate_tool", fake_translate)
    monkeypatch.setattr(
        service.publisher, "publish_spec", lambda spec, source_hash: spec
    )
    monkeypatch.setattr(
        service, "_chat_model", lambda message, context_payload, has_draft, slug: {
            "reply": "Planning now.",
            "intent": "build",
            "idea": message,
            "source_url": None,
            "suggested_name": None,
            "suggested_slug": None,
        }
    )


async def test_chat_triggers_full_pipeline(monkeypatch):
    _install_mocks(monkeypatch)
    bundle = service.create_session(idea="count words")
    session_id = bundle["session"]["id"]
    assert bundle["context"]["tool_count"] == 1

    # The chat decides the tool, so the whole pipeline runs automatically.
    bundle = await service.chat(session_id, "build a word count tool")
    assert bundle["session"]["stage"] == "published"
    assert bundle["draft"]["status"] == "published"
    assert bundle["draft"]["spec"]["slug"] == "word-count"
    assert len(bundle["draft"]["code_files"]) == 5

    pipeline = bundle["pipeline"]
    assert pipeline["running"] is False
    assert [step["status"] for step in pipeline["steps"]] == ["done"] * 6
    assert any("Decision: build" in log for log in pipeline["steps"][0]["logs"])
    assert any("no frontend" in log.lower() for log in pipeline["steps"][3]["logs"])


async def test_auto_run_reports_failed_step(monkeypatch):
    _install_mocks(monkeypatch)
    monkeypatch.setattr(
        service,
        "generate",
        lambda session_id: (_ for _ in ()).throw(
            service.StudioError("generation exploded")
        ),
    )
    bundle = service.create_session(idea="count words")
    session_id = bundle["session"]["id"]
    bundle = await service.auto_run(session_id, "count words")
    statuses = [step["status"] for step in bundle["pipeline"]["steps"]]
    assert statuses[0] == "done"
    assert statuses[2] == "error"
    assert statuses[3:] == ["skipped", "skipped", "skipped"]
    assert "exploded" in bundle["pipeline"]["steps"][2]["logs"][0].lower()


async def test_studio_code_failure_is_reported(monkeypatch):
    _install_mocks(monkeypatch, code_ok=False)
    monkeypatch.setattr(
        service.codegen,
        "generate_code",
        lambda blueprint, spec: (_ for _ in ()).throw(
            service.codegen.StudioCodegenError("all attempts failed", {"errors": ["x"]})
        ),
    )
    bundle = service.create_session(idea="count words")
    session_id = bundle["session"]["id"]
    service.research_and_plan(session_id, "count words")
    bundle = await service.generate(session_id)
    assert bundle["draft"]["status"] == "code_failed"


def test_studio_endpoints(monkeypatch):
    _install_mocks(monkeypatch)
    client = TestClient(app)

    created = client.post("/api/studio/sessions", json={"idea": "count words"})
    assert created.status_code == 200, created.text
    session_id = created.json()["session"]["id"]

    planned = client.post(
        f"/api/studio/sessions/{session_id}/plan", json={"idea": "count words"}
    )
    assert planned.status_code == 200, planned.text
    assert planned.json()["draft"]["status"] == "planned"

    generated = client.post(f"/api/studio/sessions/{session_id}/generate")
    assert generated.status_code == 200, generated.text
    assert generated.json()["draft"]["status"] == "generated"

    config = client.get("/api/studio/config")
    assert config.status_code == 200
    assert config.json()["enabled"] is True

    auto = client.post(
        f"/api/studio/sessions/{session_id}/auto-run", json={"idea": "count words"}
    )
    assert auto.status_code == 200, auto.text
    assert auto.json()["session"]["stage"] == "published"
    assert len(auto.json()["pipeline"]["steps"]) == 6
