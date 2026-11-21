"""NVIDIA NIM chat-completions wrapper for ToolSpec generation."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)


def _strip_markdown(text: str) -> str:
    """Remove ```json fences and surrounding whitespace."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def generate_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call Nemotron and parse its JSON response."""
    if not settings.nvidia_nim_api_key:
        raise RuntimeError("NVIDIA_NIM_API_KEY is not configured")
    payload = {
        "model": settings.nemotron_model,
        "temperature": 0.3,
        "max_tokens": 4000,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        response = httpx.post(
            settings.nemotron_endpoint,
            headers={
                "Authorization": f"Bearer {settings.nvidia_nim_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(_strip_markdown(content))
    except Exception as exc:
        log.error("nemotron_generation_failed", error=str(exc))
        raise
