"""Deterministic reference checks for tool examples.

The frontend tools are TypeScript, so the backend keeps small Python reference
implementations for common transformations. Unknown tools get a structural
check; the platform prompt is explicitly enforced in the generator so examples
are generated as real input/output pairs.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Callable
from urllib.parse import quote, unquote

from app.qa.rules import all_strings


def _word_counter(value: str) -> str:
    return str(len(value.split()))


def _case_upper(value: str) -> str:
    return value.upper()


def _case_lower(value: str) -> str:
    return value.lower()


def _base64_encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _base64_decode(value: str) -> str:
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


def _json_minify(value: str) -> str:
    return json.dumps(json.loads(value), separators=(",", ":"), ensure_ascii=False)


def _url_encode(value: str) -> str:
    return quote(value, safe="")


REFERENCE_FUNCTIONS: dict[str, Callable[[str], str]] = {
    "word-counter": _word_counter,
    "case-converter-upper": _case_upper,
    "case-converter-lower": _case_lower,
    "base64-encoder": _base64_encode,
    "base64-decoder": _base64_decode,
    "json-formatter": _json_minify,
    "url-encoder": _url_encode,
    "url-decoder": unquote,
}


def check_examples(spec: dict[str, Any]) -> list[str]:
    """Return QA errors for examples that are empty or demonstrably wrong."""
    errors: list[str] = []
    examples = spec.get("example") or []
    if not examples:
        return ["example: at least one real example is required"]

    slug = str(spec.get("slug", ""))
    function = REFERENCE_FUNCTIONS.get(slug)
    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            errors.append(f"example[{index}]: must be an object")
            continue
        raw_input = example.get("input")
        raw_output = example.get("output")
        if raw_input in (None, "") or raw_output in (None, ""):
            errors.append(f"example[{index}]: input and output must be non-empty")
            continue
        if function is not None:
            try:
                expected = function(str(raw_input))
            except Exception as exc:  # noqa: BLE001 - QA must never crash
                errors.append(f"example[{index}]: reference function failed ({exc})")
                continue
            if expected.strip() != str(raw_output).strip():
                errors.append(
                    f"example[{index}]: output does not match the real function "
                    f"(expected {expected!r})"
                )
    return errors


def prose_strings(spec: dict[str, Any]) -> list[str]:
    """Return only the prose fields that must not leak the category name."""
    fields: list[str] = []
    fields.append(str(spec.get("directAnswer", "")))
    about = spec.get("about") or {}
    if isinstance(about, dict):
        fields.extend(all_strings(about))
    for faq in spec.get("faqs") or []:
        if isinstance(faq, dict):
            fields.append(str(faq.get("answer", "")))
    return fields
