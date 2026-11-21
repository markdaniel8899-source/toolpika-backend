"""Groq translation wrapper with rate-limit aware retry."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

log = structlog.get_logger(__name__)


class RateLimitError(RuntimeError):
    """Raised when Groq responds with HTTP 429."""


def _strip_markdown(text: str) -> str:
    """Remove markdown code fences from a model response."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=16),
)
async def translate_json(system_prompt: str, chunk: dict[str, Any]) -> dict[str, Any]:
    """Translate one JSON chunk and return a dict with identical keys."""
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    payload = {
        "model": settings.groq_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(chunk, ensure_ascii=False)},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code == 429:
            raise RateLimitError("Groq rate limit reached")
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(_strip_markdown(content))
    except RateLimitError:
        raise
    except Exception as exc:
        log.error("groq_translation_failed", error=str(exc))
        raise


async def polite_delay() -> None:
    """Sleep between provider calls to avoid rate limiting."""
    await asyncio.sleep(max(0.0, settings.translation_call_delay_seconds))
