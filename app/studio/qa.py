"""Targeted QA for generated browser-tool code.

The checks are deliberately narrow: the generated module must be a pure
string-in / string-out operation with no network, storage, DOM or dynamic code
access. When Node.js is available the module is also executed against the
blueprint examples, so QA catches real behaviour rather than only syntax.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)

_SIGNATURE = re.compile(
    r"export\s+function\s+run\s*\(\s*input\s*:\s*string\s*\)\s*:\s*string\s*\{"
)
_JS_SIGNATURE = re.compile(
    r"export\s+function\s+run\s*\(\s*input\s*:\s*string\s*\)\s*:\s*string\s*\{"
)

_FORBIDDEN = (
    (r"(^|\n)\s*import\s", "imports are not allowed"),
    (r"\brequire\s*\(", "require() is not allowed"),
    (r"\bfetch\s*\(", "network calls are not allowed"),
    (r"\bXMLHttpRequest\b", "network calls are not allowed"),
    (r"\bWebSocket\b", "network calls are not allowed"),
    (r"\bEventSource\b", "network calls are not allowed"),
    (r"\bsendBeacon\b", "network calls are not allowed"),
    (r"\blocalStorage\b", "local storage is not allowed"),
    (r"\bsessionStorage\b", "session storage is not allowed"),
    (r"\bindexedDB\b", "IndexedDB is not allowed"),
    (r"\bdocument\.cookie\b", "cookies are not allowed"),
    (r"\beval\s*\(", "eval() is not allowed"),
    (r"\bnew\s+Function\b", "the Function constructor is not allowed"),
    (r"\bFunction\s*\(", "the Function constructor is not allowed"),
    (r"\bprocess\.", "Node process access is not allowed"),
    (r"\bwindow\.", "window access is not allowed"),
    (r"\bdocument\.", "DOM access is not allowed"),
    (r"https?://", "network URLs are not allowed"),
    (r"\balert\s*\(", "alert() is not allowed"),
    (r"\bconsole\.", "console output is not allowed"),
    (r"\bsetTimeout\s*\(", "timers are not allowed"),
    (r"\bsetInterval\s*\(", "timers are not allowed"),
    (r"\bDate\.now\b", "time-based output is not deterministic"),
    (r"while\s*\(\s*true\s*\)", "unbounded loops are not allowed"),
    (r"for\s*\(\s*;\s*;\s*\)", "unbounded loops are not allowed"),
    (r"\bdebugger\b", "debugger statements are not allowed"),
)


def _strip_fences(code: str) -> str:
    cleaned = code.strip()
    cleaned = re.sub(r"^```(?:ts|tsx|typescript|js|javascript)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def normalise_code(raw: str) -> str:
    """Extract the runnable module from a model response."""
    code = _strip_fences(raw)
    match = re.search(r"export\s+function\s+run\s*\(", code)
    if match and match.start() > 0:
        code = code[match.start() :]
    if "export function run(" not in code and "export function run (" in code:
        code = code.replace("export function run (", "export function run(")
    return code.strip()


def _static_checks(
    code: str, archetype: str
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    if not _SIGNATURE.search(code):
        errors.append(
            "module must export exactly: export function run(input: string): string"
        )
    checks["signature"] = bool(_SIGNATURE.search(code))
    checks["length"] = len(code)

    if len(code) > settings.studio_max_code_chars:
        errors.append(
            f"code is too long ({len(code)} characters, max "
            f"{settings.studio_max_code_chars})"
        )

    for pattern, message in _FORBIDDEN:
        if re.search(pattern, code):
            errors.append(message)

    if archetype != "generator" and re.search(r"\bMath\.random\b", code):
        errors.append("Math.random is only allowed for generator tools")

    if code.count("{") != code.count("}"):
        errors.append("unbalanced braces in generated code")
    if code.count("(") != code.count(")"):
        errors.append("unbalanced parentheses in generated code")

    if "TODO" in code or "FIXME" in code:
        errors.append("generated code contains an unfinished TODO/FIXME")
    if not code.rstrip().endswith("}"):
        warnings.append("generated code does not end with a closing brace")

    checks["forbidden_patterns"] = not any(
        re.search(pattern, code) for pattern, _ in _FORBIDDEN
    )
    return errors, warnings, checks


def _to_javascript(code: str) -> str:
    """Strip the only allowed TypeScript annotation (the run signature)."""
    return _JS_SIGNATURE.sub("export function run(input) {", code, count=1)


def run_node_examples(
    code: str, examples: list[dict[str, Any]], archetype: str
) -> tuple[bool, list[str], dict[str, Any]]:
    """Execute the module with Node.js against the examples, when available."""
    node = shutil.which("node")
    if not node:
        return True, [], {"node": False, "reason": "node not installed"}

    cases: list[dict[str, Any]] = []
    for example in examples[:3]:
        cases.append(
            {
                "input": str(example.get("input") or ""),
                "expected": None
                if archetype == "generator"
                else str(example.get("output") or ""),
            }
        )
    if not cases:
        cases = [{"input": "", "expected": None}]

    errors: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="toolpika-studio-") as directory:
            root = Path(directory)
            (root / "tool.mjs").write_text(_to_javascript(code), encoding="utf-8")
            runner = """
import { run } from "./tool.mjs";
const cases = JSON.parse(process.argv[2]);
const results = [];
for (const item of cases) {
  let output;
  try {
    output = run(item.input);
  } catch (error) {
    results.push({ ok: false, error: String(error && error.message ? error.message : error) });
    continue;
  }
  if (typeof output !== "string") {
    results.push({ ok: false, error: "run() did not return a string" });
    continue;
  }
  if (item.expected !== null && output !== item.expected) {
    results.push({ ok: false, error: "example output mismatch", expected: item.expected, actual: output });
    continue;
  }
  results.push({ ok: true, output });
}
console.log(JSON.stringify(results));
"""
            (root / "runner.mjs").write_text(runner, encoding="utf-8")
            completed = subprocess.run(
                [node, "runner.mjs", json.dumps(cases, ensure_ascii=False)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return False, ["generated code timed out after 20 seconds"], {"node": True}
    except Exception as exc:  # noqa: BLE001 - runtime QA must not crash the studio
        log.warning("studio_node_qa_failed", error=str(exc))
        return False, [f"could not execute generated code: {exc}"], {"node": True}

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:600]
        return (
            False,
            [f"generated code is not JavaScript-compatible: {detail}"],
            {"node": True, "returncode": completed.returncode},
        )

    try:
        results = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        return False, [f"could not read the Node.js result: {exc}"], {"node": True}

    for index, result in enumerate(results):
        if not result.get("ok"):
            message = str(result.get("error") or "runtime check failed")
            if "expected" in result:
                message += (
                    f" (expected {result.get('expected')!r}, "
                    f"got {result.get('actual')!r})"
                )
            errors.append(f"example {index + 1}: {message}")
    return not errors, errors, {"node": True, "examples_run": len(results)}


def check_code(
    code: str,
    slug: str,
    archetype: str = "text-transform",
    examples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run static and (when possible) runtime checks on generated code."""
    normalised = normalise_code(code)
    errors, warnings, checks = _static_checks(normalised, archetype)
    checks["slug"] = slug
    checks["archetype"] = archetype

    if not errors:
        runtime_ok, runtime_errors, runtime_details = run_node_examples(
            normalised, examples or [], archetype
        )
        checks["runtime"] = runtime_details
        if not runtime_ok:
            errors.extend(runtime_errors)
    else:
        checks["runtime"] = {"skipped": True}

    return {
        "ok": not errors,
        "code": normalised,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
