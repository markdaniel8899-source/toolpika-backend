"""GitHub REST client and Studio PR publishing tests (no network)."""

from __future__ import annotations

from typing import Any

import pytest

from app.services import github_client
from app.services.github_client import (
    GitHubAuthenticationError,
    GitHubBranchExistsError,
    GitHubClient,
    GitHubClientError,
)
from app.studio import codegen

TOKEN = "ghp_test_token"


class FakeResponse:
    """Minimal httpx-like response used by the mocked client."""

    def __init__(self, status_code: int, data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._data = data or {}
        self.text = str(data or "")

    def json(self) -> dict[str, Any]:
        return self._data


def _client(monkeypatch, handler) -> GitHubClient:
    client = GitHubClient(pat=TOKEN, owner="hmzain", repo="toolpika-frontend")
    monkeypatch.setattr(client, "_request", handler)
    return client


def test_require_config_lists_missing_values():
    client = GitHubClient(pat="", owner="", repo="")
    assert client.configured is False
    with pytest.raises(GitHubClientError) as exc:
        client.require_config()
    assert "GITHUB_PAT" in str(exc.value)
    assert "GITHUB_REPO_NAME" in str(exc.value)


def test_authentication_error_is_explicit(monkeypatch):
    client = GitHubClient(pat=TOKEN, owner="hmzain", repo="toolpika-frontend")

    def http_request(_method, _url, **_kwargs):
        return FakeResponse(403, {"message": "bad credentials"})

    # Patch the HTTP layer, not _request, so auth handling itself is tested.
    monkeypatch.setattr(client._client, "request", http_request)
    with pytest.raises(GitHubAuthenticationError) as exc:
        client.get_branch_sha()
    assert "authentication failed" in str(exc.value).lower()
    assert exc.value.status_code == 403


def test_get_file_decodes_base64_and_branch_exists(monkeypatch):
    calls: list[tuple[str, str]] = []

    def handler(method, path, **_kwargs):
        calls.append((method, path))
        if "ref/heads/" in path:
            return FakeResponse(200, {"object": {"sha": "abc123"}})
        return FakeResponse(
            200,
            {"content": "ZXhwb3J0IGNvbnN0IHRvb2xzID0gW107\n", "sha": "filesha"},
        )

    client = _client(monkeypatch, handler)
    assert client.get_branch_sha() == "abc123"
    assert client.branch_exists("studio/add-x") is True
    content, sha = client.get_file("src/lib/tools/registry.ts")
    assert content == "export const tools = [];"
    assert sha == "filesha"


def test_create_branch_detects_existing_branch(monkeypatch):
    def handler(method, path, **_kwargs):
        return FakeResponse(422, {"message": "Reference already exists"})

    client = _client(monkeypatch, handler)
    with pytest.raises(GitHubBranchExistsError) as exc:
        client.create_branch("studio/add-x", "abc123")
    assert exc.value.branch == "studio/add-x"


def test_publish_creates_branch_updates_existing_file_and_opens_pr(monkeypatch):
    state = {"branch_created": False, "pr_created": False}
    calls: list[str] = []

    def handler(method, path, **kwargs):
        calls.append(f"{method} {path}")
        if "ref/heads/main" in path:
            return FakeResponse(200, {"object": {"sha": "base-sha"}})
        if path == "/git/refs" and method == "POST":
            if not state["branch_created"]:
                state["branch_created"] = True
                return FakeResponse(422, {"message": "Reference already exists"})
            return FakeResponse(201, {"ref": "refs/heads/studio/add-x-ts-2"})
        if path.startswith("/contents/"):
            if method == "GET":
                if "registry.ts" in path:
                    return FakeResponse(
                        200,
                        {
                            "content": "ZXhwb3J0IGNvbnN0IHRvb2xzOiBUb29sW10gPSBbXQ==",
                            "sha": "registry-sha",
                        },
                    )
                return FakeResponse(404, {})
            return FakeResponse(
                200,
                {"content": {"sha": "new-file-sha"}, "commit": {"sha": "commit-sha"}},
            )
        if path == "/pulls" and method == "POST":
            state["pr_created"] = True
            return FakeResponse(201, {"number": 42, "html_url": "https://github.com/pr/42"})
        if path == "/pulls/42/merge":
            return FakeResponse(200, {"merged": True})
        return FakeResponse(200, {})

    client = _client(monkeypatch, handler)
    files = [
        {"path": "src/components/tools/x-tool.tsx", "content": "component", "kind": "component"},
        {
            "path": "src/lib/tools/registry.ts",
            "content": "export const tools: Tool[] = [\n  // new\n];\n",
            "kind": "registry",
        },
        {
            "path": "src/components/tools/generated-components.tsx",
            "content": "map",
            "kind": "registry",
        },
    ]
    result = client.publish(
        "x",
        files,
        "Studio: add X",
        "Generated body",
        auto_merge=True,
    )

    assert result["success"] is True
    assert result["pr_url"] == "https://github.com/pr/42"
    assert result["pr_number"] == 42
    assert result["merged"] is True
    assert result["branch"].startswith("studio/add-x-")
    assert len(result["files"]) == 3
    assert "PUT /contents/src/lib/tools/registry.ts" in calls


def test_component_and_registry_helpers():
    code = "export function run(input: string): string { return input; }"
    blueprint = {
        "slug": "word-count",
        "name": "Word Count",
        "category": "text",
        "archetype": "text-analyzer",
        "input_label": "Text",
        "input_placeholder": "Paste text",
        "run_label": "Count",
        "output_label": "Words",
        "examples": [],
    }
    component = codegen.render_component_tsx(blueprint, code)
    assert "function run(input: string): string" in component
    assert "export function run" not in component
    assert "GeneratedToolWorkspace" in component
    assert "export default function WordCountTool()" in component

    registry = "export const tools: Tool[] = [\n  { slug: \"old\" },\n];\n"
    updated = codegen.register_tool_in_registry(
        registry, blueprint, {"name": "Word Count", "seo": {"description": "d"}}
    )
    assert updated != registry
    assert 'slug: "word-count"' in updated
    # Re-applying the same tool is a no-op.
    assert codegen.register_tool_in_registry(
        updated, blueprint, {"name": "Word Count"}
    ) == updated

    component_map = codegen.register_generated_component("", "word-count")
    assert '"word-count": dynamic(() => import("./word-count-tool")' in component_map
    assert codegen.register_generated_component(component_map, "word-count") == component_map
