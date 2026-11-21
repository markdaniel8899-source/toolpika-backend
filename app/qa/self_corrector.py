"""Send QA failures back to Nemotron for a corrected ToolSpec."""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings
from app.services import nemotron_client
from app.templates.tool_template import load_template_markdown

log = structlog.get_logger(__name__)


def correct_spec(spec: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Ask the model to repair a spec using the exact QA error list."""
    system_prompt = (
        f"{load_template_markdown()}\n\n"
        "You are fixing a tool spec that failed QA. "
        "Output ONLY valid JSON with the same structure. No markdown wrappers."
    )
    user_prompt = (
        "Current JSON:\n"
        f"{spec}\n\n"
        "QA errors to fix:\n"
        + "\n".join(f"- {error}" for error in errors)
        + "\n\nFix these issues. Output ONLY valid JSON."
    )
    try:
        corrected = nemotron_client.generate_json(system_prompt, user_prompt)
        log.info("self_correction_applied", fixes=len(errors))
        return corrected
    except Exception as exc:
        log.error("self_correction_failed", error=str(exc))
        raise


def max_attempts() -> int:
    """Return the configured maximum number of QA attempts."""
    return settings.qa_max_retries
