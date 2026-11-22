"""Studio code QA and blueprint tests."""

from __future__ import annotations

import shutil

from app.studio import codegen, planner, qa

VALID_CODE = """export function run(input: string): string {
  const words = input.trim().split(/\\s+/).filter(Boolean);
  return String(words.length);
}
"""


def test_normalise_code_removes_fences():
    code = qa.normalise_code("```ts\n" + VALID_CODE + "\n```")
    assert code.startswith("export function run(")
    assert "```" not in code


def test_check_code_accepts_valid_module():
    result = qa.check_code(
        VALID_CODE,
        "word-count",
        "text-analyzer",
        [{"input": "hello world", "output": "2"}],
    )
    assert result["ok"] is True, result["errors"]
    assert result["code"] == VALID_CODE.strip()


def test_check_code_rejects_network_calls():
    code = VALID_CODE.replace(
        "return String(words.length);",
        'return fetch("https://example.com");',
    )
    result = qa.check_code(code, "bad-tool", "text-transform")
    assert result["ok"] is False
    assert any("network" in error.lower() for error in result["errors"])


def test_check_code_rejects_wrong_signature():
    result = qa.check_code(
        "function run(input: string): string { return input; }", "bad-tool"
    )
    assert result["ok"] is False
    assert any("export" in error for error in result["errors"])


def test_check_code_runtime_example_mismatch():
    if not shutil.which("node"):
        return
    result = qa.check_code(
        VALID_CODE,
        "word-count",
        "text-analyzer",
        [{"input": "hello world", "output": "99"}],
    )
    assert result["ok"] is False
    assert any("mismatch" in error for error in result["errors"])


def test_slugify_and_fallback_blueprint():
    assert planner.slugify("Hello World / Tool!") == "hello-world-tool"
    context = {
        "site": {
            "tools": [
                {"slug": "word-counter", "name": "Word Counter"},
                {"slug": "base64-encoder", "name": "Base64 Encoder"},
            ]
        }
    }
    research = {
        "idea": "text word count tool",
        "summary": "Count words in your text. It is quick.",
        "features": ["Fast", "Local"],
        "suggested_name": "Text Word Counter",
        "suggested_slug": "text-word-counter",
    }
    blueprint = planner.fallback_blueprint(research, context)
    assert blueprint["slug"] == "text-word-counter"
    assert blueprint["name"] == "Text Word Counter"
    assert len(blueprint["features"]) >= 3
    assert set(blueprint["related_tools"]) <= {"word-counter", "base64-encoder"}


def test_generate_blueprint_falls_back_when_model_fails(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(planner.nemotron_client, "generate_json", boom)
    context = {"site": {"tools": [{"slug": "word-counter", "name": "Word Counter"}]}}
    result = planner.generate_blueprint(
        {"idea": "word counter", "suggested_name": "Word Counter"}, context
    )
    assert result["slug"]


def test_build_files_contains_all_runtime_files():
    blueprint = {
        "slug": "word-count",
        "name": "Word Count",
        "category": "text",
        "archetype": "text-analyzer",
        "description": "Count words.",
        "input_label": "Text",
        "input_placeholder": "Paste text",
        "run_label": "Count",
        "output_label": "Numbers",
        "examples": [],
        "icon": "Wand2",
    }
    spec = {
        "name": "Word Count",
        "directAnswer": "A short answer.",
        "seo": {"description": "Meta description."},
        "about": {"whatIs": "A tool.", "useCases": ["A"], "commonMistakes": ["B"]},
        "faqs": [{"question": "Q?", "answer": "A."}],
    }
    built = codegen.build_files(blueprint, spec, VALID_CODE)
    paths = {item["path"] for item in built["files"]}
    assert "src/lib/tools/generated/word-count.ts" in paths
    assert "src/lib/tools/generated/manifest.json" in paths
    assert "src/lib/tools/generated/tools.ts" in paths
    assert "src/lib/tools/generated/registry.ts" in paths
    assert "src/lib/tools/generated/content.ts" in paths
    assert "runWordCount" in built["files"][3]["content"]
    assert "getGeneratedToolContent" in built["files"][4]["content"]
