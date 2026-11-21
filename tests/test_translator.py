"""Translator chunking and rate-limit behaviour tests."""

from __future__ import annotations

import asyncio

from app.pipelines import translator
from app.services import groq_client
from tests.conftest import make_spec


def test_chunks_cover_all_fields(spec):
    chunks = translator.build_chunks(spec)
    assert set(chunks) == set(translator.CHUNKS)
    assert "title" in chunks["seo"]
    assert "directAnswer" in chunks["core"]
    assert "whatIs" in chunks["deep"]
    assert "faqs" in chunks["faqs"]


def test_prompt_has_seo_limit():
    prompt = translator.build_prompt("de", "seo")
    assert "60 characters" in prompt
    assert "155" in prompt


def test_prompt_keeps_glossary():
    prompt = translator.build_prompt("fr", "core")
    assert "Toolpika" in prompt
    assert "Base64" in prompt


def test_strip_markdown():
    assert groq_client._strip_markdown("```json\n{\"a\":1}\n```") == '{"a":1}'


def test_polite_delay_configured_zero():
    asyncio.run(groq_client.polite_delay())


def test_translate_tool_happy_path(monkeypatch, spec):
    monkeypatch.setattr(
        translator.supabase_client, "select", lambda *a: [{"slug": "word-counter", "spec": spec}]
    )
    saved = []
    monkeypatch.setattr(
        translator.supabase_client,
        "upsert",
        lambda table, rows, on_conflict: saved.extend(rows) or rows,
    )
    calls = []

    async def fake_translate(prompt, chunk):
        calls.append(1)
        return {key: "übersetzt" for key in chunk}

    monkeypatch.setattr(translator.groq_client, "translate_json", fake_translate)
    result = asyncio.run(translator.translate_tool("word-counter", ["de"]))
    assert result.translated_locales == ["de"]
    assert result.failed_locales == []
    assert len(calls) == 4
    assert len(saved) == 5


def test_translate_tool_missing_spec(monkeypatch):
    monkeypatch.setattr(translator.supabase_client, "select", lambda *a: [])
    result = asyncio.run(translator.translate_tool("missing", ["de"]))
    assert result.failed_locales == ["de"]
    assert result.errors


def test_rate_limit_error_type():
    assert issubclass(groq_client.RateLimitError, RuntimeError)
