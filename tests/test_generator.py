"""Generator pipeline tests with mocked Nemotron responses."""

from __future__ import annotations

from app.pipelines import generator
from app.services import nemotron_client
from tests.conftest import make_spec


def test_strip_markdown_fences():
    assert nemotron_client._strip_markdown("```json\n{\"a\": 1}\n```") == '{"a": 1}'


def test_system_prompt_contains_template_rules():
    prompt = generator.build_system_prompt()
    assert "UNIVERSAL_TOOL_TEMPLATE.md" in prompt
    assert "40-43" in prompt


def test_user_prompt_contains_research(research):
    prompt = generator.build_user_prompt(research)
    assert research.topic in prompt
    assert research.demand_signal in prompt


def test_generate_returns_payload(monkeypatch, research):
    payload = make_spec()
    monkeypatch.setattr(generator.nemotron_client, "generate_json", lambda *a: payload)
    assert generator.generate_tool_spec(research) == payload


def test_generate_retries_missing_keys(monkeypatch, research):
    calls = []

    def fake(*args):
        calls.append(1)
        return {"slug": "x"} if len(calls) == 1 else make_spec()

    monkeypatch.setattr(generator.nemotron_client, "generate_json", fake)
    assert generator.generate_tool_spec(research)["slug"] == "word-counter"
    assert len(calls) == 2


def test_generate_raises_after_retries(monkeypatch, research):
    monkeypatch.setattr(
        generator.nemotron_client,
        "generate_json",
        lambda *a: {"slug": "x"},
    )
    try:
        generator.generate_tool_spec(research)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")


def test_required_keys_constant():
    assert "directAnswer" in generator.REQUIRED_TOP_KEYS
    assert "seo" in generator.REQUIRED_TOP_KEYS
