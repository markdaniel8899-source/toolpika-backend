"""Code generation and frontend file application for Tool Studio.

A generated tool is a small, pure TypeScript module:

    export function run(input: string): string

The generic ``GeneratedTool`` workspace renders it, so the model never writes
React or touches the DOM. The module is validated by ``app.studio.qa`` before
any file is written.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from app.config import settings
from app.services import nemotron_client
from app.studio import qa

log = structlog.get_logger(__name__)

GENERATED_DIR = Path("src/lib/tools/generated")
MANIFEST_PATH = GENERATED_DIR / "manifest.json"

# GitHub PR publishing targets (paths are relative to the frontend repository).
COMPONENT_PATH_TEMPLATE = "src/components/tools/{slug}-tool.tsx"
REGISTRY_PATH = "src/lib/tools/registry.ts"
COMPONENT_MAP_PATH = "src/components/tools/generated-components.tsx"


class StudioCodegenError(RuntimeError):
    """Raised when no usable code can be generated."""

    def __init__(self, message: str, qa_result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.qa_result = qa_result or {}


def _identifier(slug: str, used: set[str]) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", slug) if part]
    name = "".join(part[:1].upper() + part[1:] for part in parts) or "Tool"
    if name[0].isdigit():
        name = f"Tool{name}"
    identifier = f"run{name}"
    if identifier in used:
        index = 2
        while f"{identifier}{index}" in used:
            index += 1
        identifier = f"{identifier}{index}"
    used.add(identifier)
    return identifier


def _examples(blueprint: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, str]]:
    raw = blueprint.get("examples") or spec.get("example") or []
    examples: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            examples.append(
                {
                    "input": str(item.get("input") or ""),
                    "output": str(item.get("output") or ""),
                }
            )
    return examples[:3]


def _code_prompt(
    blueprint: dict[str, Any],
    spec: dict[str, Any],
    examples: list[dict[str, str]],
    previous_errors: list[str] | None = None,
) -> str:
    contract = (
        "Write one dependency-free TypeScript module for a browser tool.\n"
        "The module must export exactly this function:\n"
        "  export function run(input: string): string\n"
        "Rules:\n"
        "- Pure function: no imports, network, storage, DOM, timers, eval or dynamic code.\n"
        "- Plain JavaScript-compatible TypeScript: only the run signature may have\n"
        "  type annotations. Do not use interfaces, type aliases, generics, enums,\n"
        "  `as` assertions or annotations inside the function body.\n"
        "- Handle empty or malformed input by returning a helpful string, never by\n"
        "  throwing for normal input.\n"
        "- Return a string. Use \\n for multiple lines. No HTML.\n"
        "- Be deterministic. Math.random is only allowed for generator tools.\n"
        "- Keep the module under "
        f"{settings.studio_max_code_chars} characters.\n"
        "- The function must actually implement the tool, not describe it.\n"
        "Return ONLY JSON with keys: code (string), notes (string).\n"
    )
    payload = {
        "tool": {
            "slug": blueprint.get("slug"),
            "name": blueprint.get("name"),
            "category": blueprint.get("category"),
            "archetype": blueprint.get("archetype"),
            "description": blueprint.get("description"),
            "input_label": blueprint.get("input_label"),
            "output_label": blueprint.get("output_label"),
            "features": blueprint.get("features"),
        },
        "spec_examples": examples,
        "spec_features": spec.get("features") or [],
        "spec_how_to_use": spec.get("howToUse") or [],
    }
    prompt = contract + "\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    if previous_errors:
        prompt += (
            "\n\nThe previous attempt failed QA. Fix every issue below and return a "
            "complete replacement module:\n"
            + "\n".join(f"- {error}" for error in previous_errors)
        )
    return prompt


def generate_code(
    blueprint: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Generate and QA the runnable module, retrying with the QA errors."""
    examples = _examples(blueprint, spec)
    archetype = str(blueprint.get("archetype") or "text-transform")
    errors: list[str] = []
    last_result: dict[str, Any] = {}
    attempts = max(1, settings.qa_max_retries)

    for attempt in range(1, attempts + 1):
        try:
            payload = nemotron_client.generate_json(
                "You are a senior TypeScript engineer. You write small, correct, "
                "privacy-first browser utilities. Return only the requested JSON.",
                _code_prompt(blueprint, spec, examples, errors or None),
                model=settings.studio_codegen_model or None,
                temperature=0.2,
                max_tokens=6000,
            )
        except Exception as exc:  # noqa: BLE001 - retry model failures
            errors = [f"model call failed: {exc}"]
            log.warning(
                "studio_codegen_call_failed",
                slug=blueprint.get("slug"),
                attempt=attempt,
                error=str(exc),
            )
            continue

        raw_code = str(payload.get("code") or "")
        result = qa.check_code(raw_code, str(blueprint.get("slug") or ""), archetype, examples)
        result["notes"] = str(payload.get("notes") or "")[:1000]
        result["attempts"] = attempt
        last_result = result
        if result["ok"]:
            log.info(
                "studio_code_generated",
                slug=blueprint.get("slug"),
                attempt=attempt,
                length=len(result["code"]),
            )
            return result
        errors = list(result["errors"])
        log.warning(
            "studio_code_qa_failed",
            slug=blueprint.get("slug"),
            attempt=attempt,
            errors=errors,
        )

    raise StudioCodegenError(
        "code generation failed after "
        f"{attempts} attempts: " + "; ".join(errors[:6]),
        last_result,
    )


def _paragraphs(text: str, max_paragraphs: int = 3) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    if len(parts) == 1 and len(parts[0]) > 700:
        sentences = re.split(r"(?<=[.!?])\s+", parts[0])
        midpoint = max(1, len(sentences) // 2)
        parts = [" ".join(sentences[:midpoint]), " ".join(sentences[midpoint:])]
    return [part[:1600] for part in parts[:max_paragraphs]]


def build_content(spec: dict[str, Any]) -> dict[str, Any]:
    """Turn a ToolSpec into the article + FAQ shape used by the tool page."""
    name = str(spec.get("name") or "This tool")
    about = spec.get("about") or {}
    intro = str(spec.get("directAnswer") or "").strip()
    if not intro:
        intro = _paragraphs(str(about.get("whatIs") or ""), 1)[0] if about.get("whatIs") else ""

    sections: list[dict[str, Any]] = []
    what_is = _paragraphs(str(about.get("whatIs") or ""))
    if what_is:
        sections.append({"heading": f"What is {name}?", "paragraphs": what_is})

    use_cases = [
        " ".join(str(item).split())[:600]
        for item in about.get("useCases") or []
        if str(item).strip()
    ]
    if use_cases:
        sections.append({"heading": f"Common uses for {name}", "paragraphs": use_cases})

    mistakes = [
        " ".join(str(item).split())[:600]
        for item in about.get("commonMistakes") or []
        if str(item).strip()
    ]
    if mistakes:
        sections.append({"heading": "Mistakes to avoid", "paragraphs": mistakes})

    limits = [
        " ".join(str(item).split())[:600]
        for item in about.get("limits") or []
        if str(item).strip()
    ]
    if limits:
        sections.append({"heading": "Limits to know", "paragraphs": limits})

    if not sections:
        sections.append(
            {
                "heading": f"About {name}",
                "paragraphs": [
                    str(spec.get("seo", {}).get("description") or intro or name)
                ],
            }
        )

    faqs = [
        {
            "question": " ".join(str(faq.get("question") or "").split())[:300],
            "answer": " ".join(str(faq.get("answer") or "").split())[:2000],
        }
        for faq in spec.get("faqs") or []
        if isinstance(faq, dict) and str(faq.get("question") or "").strip()
    ]

    return {"intro": intro, "sections": sections, "faqs": faqs}


def _manifest_entry(
    blueprint: dict[str, Any],
    spec: dict[str, Any],
    content: dict[str, Any],
) -> dict[str, Any]:
    seo = spec.get("seo") or {}
    return {
        "slug": blueprint["slug"],
        "title": str(spec.get("name") or blueprint["name"]),
        "category": blueprint["category"],
        "description": str(
            seo.get("description") or blueprint.get("description") or ""
        )[:300],
        "icon": str(blueprint.get("icon") or "Wand2"),
        "inputs": ["text"],
        "archetype": blueprint.get("archetype") or "text-transform",
        "inputLabel": blueprint.get("input_label") or "Input",
        "inputPlaceholder": blueprint.get("input_placeholder") or "Paste your content here.",
        "runLabel": blueprint.get("run_label") or "Run",
        "outputLabel": blueprint.get("output_label") or "Result",
        "examples": _examples(blueprint, spec),
        "content": content,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _json(value: Any, indent: int = 2) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent)


def render_tools_ts(tools: list[dict[str, Any]]) -> str:
    entries = []
    for tool in tools:
        entries.append(
            "  {\n"
            f'    id: {json.dumps(tool["slug"])},\n'
            f'    slug: {json.dumps(tool["slug"])},\n'
            f'    title: {json.dumps(tool["title"], ensure_ascii=False)},\n'
            f'    category: {json.dumps(tool["category"])},\n'
            f'    description: {json.dumps(tool["description"], ensure_ascii=False)},\n'
            f'    icon: {json.dumps(tool["icon"])},\n'
            f'    inputs: {json.dumps(tool["inputs"])},\n'
            "    clientSide: true,\n"
            '    status: "live",\n'
            "  },"
        )
    return (
        "/* Generated by Toolpika Studio. Do not edit by hand. */\n"
        'import type { Tool } from "@/lib/tools/registry";\n\n'
        "export const generatedTools: Tool[] = [\n"
        + "\n".join(entries)
        + ("\n" if entries else "")
        + "];\n"
    )


def render_registry_ts(tools: list[dict[str, Any]]) -> str:
    used: set[str] = set()
    imports: list[str] = []
    runners: list[str] = []
    meta: list[str] = []
    for tool in tools:
        slug = str(tool["slug"])
        identifier = _identifier(slug, used)
        imports.append(f'import {{ run as {identifier} }} from "./{slug}";')
        runners.append(f"  {json.dumps(slug)}: {identifier},")
        meta.append(
            "  "
            + json.dumps(slug)
            + ": {\n"
            + f'    slug: {json.dumps(slug)},\n'
            + f'    title: {json.dumps(tool["title"], ensure_ascii=False)},\n'
            + f'    archetype: {json.dumps(tool["archetype"])},\n'
            + f'    inputLabel: {json.dumps(tool["inputLabel"], ensure_ascii=False)},\n'
            + f'    inputPlaceholder: {json.dumps(tool["inputPlaceholder"], ensure_ascii=False)},\n'
            + f'    runLabel: {json.dumps(tool["runLabel"], ensure_ascii=False)},\n'
            + f'    outputLabel: {json.dumps(tool["outputLabel"], ensure_ascii=False)},\n'
            + f'    examples: {json.dumps(tool["examples"], ensure_ascii=False)},\n'
            + "  },"
        )

    return (
        "/* Generated by Toolpika Studio. Do not edit by hand. */\n"
        + ("\n".join(imports) + "\n\n" if imports else "")
        + "export type GeneratedRunner = (input: string) => string;\n\n"
        "export interface GeneratedToolMeta {\n"
        "  slug: string;\n"
        "  title: string;\n"
        "  archetype: string;\n"
        "  inputLabel: string;\n"
        "  inputPlaceholder: string;\n"
        "  runLabel: string;\n"
        "  outputLabel: string;\n"
        "  examples: { input: string; output: string }[];\n"
        "}\n\n"
        "export const generatedToolMeta: Record<string, GeneratedToolMeta> = {\n"
        + "\n".join(meta)
        + ("\n" if meta else "")
        + "};\n\n"
        "export const generatedRunners: Record<string, GeneratedRunner> = {\n"
        + "\n".join(runners)
        + ("\n" if runners else "")
        + "};\n\n"
        "export function hasGeneratedTool(slug: string): boolean {\n"
        "  return slug in generatedRunners;\n"
        "}\n\n"
        "export function getGeneratedToolMeta(slug: string): GeneratedToolMeta | undefined {\n"
        "  return generatedToolMeta[slug];\n"
        "}\n\n"
        "export function getGeneratedRunner(slug: string): GeneratedRunner | undefined {\n"
        "  return generatedRunners[slug];\n"
        "}\n"
    )


def render_content_ts(tools: list[dict[str, Any]]) -> str:
    content = {str(tool["slug"]): tool.get("content") or {} for tool in tools}
    return (
        "/* Generated by Toolpika Studio. Do not edit by hand. */\n"
        'import type { ToolSeoContent } from "@/lib/tools/seo-content";\n\n'
        "export const generatedToolContent: Record<string, ToolSeoContent> = "
        + _json(content)
        + ";\n\n"
        "export function getGeneratedToolContent(slug: string): ToolSeoContent | undefined {\n"
        "  return generatedToolContent[slug];\n"
        "}\n"
    )


def empty_manifest() -> dict[str, Any]:
    return {"version": 1, "tools": []}


def load_manifest(frontend_path: Path | None) -> dict[str, Any]:
    if not frontend_path:
        return empty_manifest()
    path = frontend_path / MANIFEST_PATH
    if not path.exists():
        return empty_manifest()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - a broken manifest should not block
        log.warning("studio_manifest_read_failed", path=str(path), error=str(exc))
        return empty_manifest()
    if not isinstance(payload, dict) or not isinstance(payload.get("tools"), list):
        return empty_manifest()
    payload.setdefault("version", 1)
    return payload


def build_files(
    blueprint: dict[str, Any],
    spec: dict[str, Any],
    code: str,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the generated module and the registry files without writing them."""
    content = build_content(spec)
    entry = _manifest_entry(blueprint, spec, content)
    current = manifest or empty_manifest()
    tools = [
        item
        for item in current.get("tools") or []
        if isinstance(item, dict) and item.get("slug") != blueprint["slug"]
    ]
    tools.append(entry)
    tools.sort(key=lambda item: str(item.get("slug") or ""))
    updated = {"version": 1, "tools": tools}

    files = [
        {
            "path": (GENERATED_DIR / f"{blueprint['slug']}.ts").as_posix(),
            "content": code.rstrip() + "\n",
            "kind": "module",
        },
        {
            "path": MANIFEST_PATH.as_posix(),
            "content": _json(updated) + "\n",
            "kind": "manifest",
        },
        {
            "path": (GENERATED_DIR / "tools.ts").as_posix(),
            "content": render_tools_ts(tools),
            "kind": "registry",
        },
        {
            "path": (GENERATED_DIR / "registry.ts").as_posix(),
            "content": render_registry_ts(tools),
            "kind": "registry",
        },
        {
            "path": (GENERATED_DIR / "content.ts").as_posix(),
            "content": render_content_ts(tools),
            "kind": "content",
        },
    ]
    return {
        "files": files,
        "manifest": updated,
        "entry": entry,
        "content": content,
    }


def resolve_frontend_path() -> Path | None:
    """Find the frontend checkout, if this deployment has one."""
    if settings.studio_frontend_path:
        candidate = Path(settings.studio_frontend_path).expanduser()
        if candidate.is_dir():
            return candidate.resolve()
        log.warning("studio_frontend_path_missing", path=str(candidate))
        return None

    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "frontend",
        here.parents[2] / "frontend",
        Path("/app/frontend"),
    ]
    for candidate in candidates:
        if (candidate / "package.json").exists():
            return candidate.resolve()
    return None


def apply_files(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Write generated files into the frontend checkout when one is available."""
    root = resolve_frontend_path()
    if not root:
        return {
            "applied": False,
            "reason": (
                "No frontend checkout is configured on this server. Set "
                "STUDIO_FRONTEND_PATH or run the apply step from the local "
                "development environment."
            ),
            "written": [],
        }

    written: list[str] = []
    for item in files:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise StudioCodegenError(f"unsafe generated path: {relative}")
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise StudioCodegenError(f"generated path escapes the frontend: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(str(item["content"]))
        written.append(str(relative).replace("\\", "/"))

    log.info("studio_files_applied", root=str(root), count=len(written))
    return {"applied": True, "root": str(root), "written": written}


# ---------------------------------------------------------------------------
# GitHub PR publishing helpers
# ---------------------------------------------------------------------------


def _component_name(slug: str) -> str:
    """Build a valid PascalCase React component name from a tool slug."""
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", slug) if part]
    name = "".join(part[:1].upper() + part[1:] for part in parts) or "Tool"
    if name[0].isdigit():
        name = f"Tool{name}"
    return f"{name}Tool"


def render_component_tsx(blueprint: dict[str, Any], code: str) -> str:
    """Wrap the QA-passed ``run`` function in a self-contained React component.

    The UI itself lives in the shared ``GeneratedToolWorkspace`` component, so
    this file contains only generated logic and metadata. No dynamic code or
    arbitrary React from the model is shipped to visitors.
    """
    slug = str(blueprint["slug"])
    internal = re.sub(
        r"^\s*export\s+function\s+run",
        "function run",
        (code or "").strip(),
        count=1,
        flags=re.MULTILINE,
    )
    if not internal.startswith("function run"):
        raise StudioCodegenError("Generated code must export a run() function.")

    meta = {
        "slug": slug,
        "title": blueprint.get("name") or slug,
        "archetype": blueprint.get("archetype") or "text-transform",
        "inputLabel": blueprint.get("input_label") or "Input",
        "inputPlaceholder": blueprint.get("input_placeholder") or "Paste your content here.",
        "runLabel": blueprint.get("run_label") or "Run",
        "outputLabel": blueprint.get("output_label") or "Result",
        "examples": blueprint.get("examples") or [],
    }
    return "\n".join(
        [
            '"use client";',
            "",
            'import { GeneratedToolWorkspace } from "@/components/tools/workspaces/generated-tool";',
            "",
            internal,
            "",
            f"const meta = {json.dumps(meta, ensure_ascii=False, indent=2)};",
            "",
            f"export default function {_component_name(slug)}() {{",
            f'  return <GeneratedToolWorkspace slug="{slug}" run={{run}} meta={{meta}} />;',
            "}",
            "",
        ]
    )


def _registry_entry(blueprint: dict[str, Any], spec: dict[str, Any]) -> str:
    """Render one Tool entry for the static frontend registry."""
    slug = str(blueprint["slug"])
    seo = spec.get("seo") or {}
    return (
        "  {\n"
        f"    id: {json.dumps(slug)},\n"
        f"    slug: {json.dumps(slug)},\n"
        f"    title: {json.dumps(str(spec.get('name') or blueprint.get('name') or slug), ensure_ascii=False)},\n"
        f"    category: {json.dumps(str(blueprint.get('category') or 'text'))},\n"
        f"    description: {json.dumps(str(seo.get('description') or blueprint.get('description') or ''), ensure_ascii=False)},\n"
        f"    icon: {json.dumps(str(blueprint.get('icon') or 'Wand2'))},\n"
        f"    inputs: {json.dumps(['text'])},\n"
        "    clientSide: true,\n"
        '    status: "live",\n'
        "  },\n"
    )


def register_tool_in_registry(
    source: str, blueprint: dict[str, Any], spec: dict[str, Any]
) -> str:
    """Insert a tool into ``registry.ts`` without duplicating an existing slug."""
    slug = str(blueprint["slug"])
    if f'slug: "{slug}"' in source or f'id: "{slug}"' in source:
        return source
    marker = "export const tools: Tool[] = ["
    start = source.find(marker)
    if start < 0:
        raise StudioCodegenError(f"Cannot find the tools array in {REGISTRY_PATH}")
    insert_at = source.find("\n", start)
    if insert_at < 0:
        raise StudioCodegenError(f"Malformed tools array in {REGISTRY_PATH}")
    return source[: insert_at + 1] + _registry_entry(blueprint, spec) + source[insert_at + 1 :]


_COMPONENT_MAP_HEADER = '''"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import { WorkspaceSkeleton } from "@/components/ui/skeleton";

const loading = () => <WorkspaceSkeleton />;

export const generatedComponents: Record<string, ComponentType> = {
'''

_COMPONENT_MAP_FOOTER = "};\n"


def register_generated_component(source: str, slug: str) -> str:
    """Add a slug to the dynamic component map, creating the file if needed."""
    safe = re.sub(r"[^a-zA-Z0-9-]", "", slug)
    if not source.strip():
        source = _COMPONENT_MAP_HEADER + _COMPONENT_MAP_FOOTER
    if f'"{slug}": dynamic(' in source:
        return source
    marker = "export const generatedComponents: Record<string, ComponentType> = {\n"
    start = source.find(marker)
    if start < 0:
        raise StudioCodegenError(f"Malformed generated component map in {COMPONENT_MAP_PATH}")
    insert_at = start + len(marker)
    line = f'  "{slug}": dynamic(() => import("./{safe}-tool"), {{ loading }}),\n'
    return source[:insert_at] + line + source[insert_at:]


def build_github_files(
    blueprint: dict[str, Any],
    spec: dict[str, Any],
    code: str,
    registry_source: str,
    component_map_source: str,
) -> list[dict[str, str]]:
    """Build the three files committed in the GitHub PR."""
    slug = str(blueprint["slug"])
    return [
        {
            "path": COMPONENT_PATH_TEMPLATE.format(slug=slug),
            "content": render_component_tsx(blueprint, code),
            "kind": "component",
        },
        {
            "path": REGISTRY_PATH,
            "content": register_tool_in_registry(registry_source, blueprint, spec),
            "kind": "registry",
        },
        {
            "path": COMPONENT_MAP_PATH,
            "content": register_generated_component(component_map_source, slug),
            "kind": "registry",
        },
    ]
