"""AI Strategist: RAG-aware chat with intent routing into the research pipeline."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.config import settings
from app.pipelines.research_scout import run_research_scout
from app.services.context_builder import get_existing_tools_context

log = structlog.get_logger(__name__)

RESEARCH_HINT = re.compile(
    r"\b(research|scout|trend(?:ing|s)?|find\s+(?:tool\s+)?ideas?|market\s+scan)\b",
    re.IGNORECASE,
)


class ChatEngineError(RuntimeError):
    """Raised when the strategist model cannot be reached."""


@dataclass
class ChatResult:
    """Outcome of one strategist turn."""

    reply: str
    action: str = "chat"
    topic: str | None = None
    ideas: list[dict[str, Any]] = field(default_factory=list)
    research: dict[str, Any] = field(default_factory=dict)
    context_tool_count: int = 0


def build_system_prompt(existing_tools_context: str) -> str:
    """Build the RAG system prompt from the live tool catalogue."""
    return (
        "You are Toolpika's AI Strategist. \n"
        f"Current existing tools in our database: {existing_tools_context}\n"
        "Rules: \n"
        "1. Never suggest building a tool that already exists in the list above.\n"
        '2. If the user asks to research or find trends, output a specific JSON command: {"action": "run_research", "topic": "..."}.\n'
        "3. Otherwise, reply conversationally, giving strategic advice on tool building, SEO, and market demand.\n"
        "Keep chat replies concise and practical. Return only the JSON command when researching."
    )


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_decision(raw: str, message: str, mode: str | None) -> tuple[str, str | None, str]:
    """Return (action, topic, conversational_reply) from a model response."""
    cleaned = _strip_fences(raw)
    payload: dict[str, Any] | None = None
    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        candidates.append(cleaned[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:  # noqa: BLE001 - plain text replies are expected
            continue
        if isinstance(parsed, dict):
            payload = parsed
            break

    action = ""
    topic: str | None = None
    if payload:
        action = str(payload.get("action") or "").strip().lower()
        topic = str(payload.get("topic") or "").strip() or None

    if mode == "research" or action == "run_research":
        return "run_research", topic or message.strip() or None, ""

    reply = cleaned
    if not reply:
        reply = "I can help you evaluate tool ideas, spot gaps and plan research."
    if not action and mode != "research" and RESEARCH_HINT.search(message):
        # Safety net if the model answered in prose to an obvious research command.
        return "run_research", message.strip() or None, ""
    return "chat", None, reply


def _call_model(messages: list[dict[str, str]]) -> str:
    """Send the RAG prompt to Nemotron via httpx and return its text."""
    if not settings.nvidia_nim_api_key:
        raise ChatEngineError("NVIDIA_NIM_API_KEY is not configured.")
    try:
        response = httpx.post(
            settings.nemotron_endpoint,
            headers={
                "Authorization": f"Bearer {settings.nvidia_nim_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.nemotron_model,
                "temperature": 0.4,
                "max_tokens": 1800,
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": messages,
            },
            timeout=90.0,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"] or "")
    except Exception as exc:  # noqa: BLE001
        raise ChatEngineError(f"Strategist model call failed: {exc}") from exc


def _fallback_reply(message: str) -> tuple[str, str | None, str]:
    """Offline behaviour when the model is unavailable."""
    if RESEARCH_HINT.search(message):
        return "run_research", message.strip() or None, ""
    return (
        "chat",
        None,
        "I can see the live tool catalogue in context. Ask me about a tool idea, "
        "SEO angle or market demand, or tell me to research trending tools.",
    )


async def handle_chat(
    message: str,
    mode: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> ChatResult:
    """Handle one admin chat turn, optionally triggering the research pipeline."""
    message = (message or "").strip()
    if not message:
        raise ChatEngineError("Write a message first.")

    tools_context = await asyncio.to_thread(get_existing_tools_context)
    system_prompt = build_system_prompt(tools_context)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in (history or [])[-10:]:
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = str(item.get("content") or "").strip()[:2000]
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    try:
        raw = await asyncio.to_thread(_call_model, messages)
    except ChatEngineError as exc:
        log.warning("strategist_model_failed", error=str(exc))
        action, topic, reply = _fallback_reply(message)
    else:
        action, topic, reply = _parse_decision(raw, message, mode)

    tool_count = len(re.findall(r"^- ", tools_context, flags=re.MULTILINE))
    if action != "run_research":
        return ChatResult(reply=reply, action="chat", context_tool_count=tool_count)

    log.info("strategist_triggered_research", topic=topic)
    result = await run_research_scout(topic)
    return ChatResult(
        reply=(
            f"Research complete. I scouted {result.sources_count} sources and saved "
            f"{len(result.ideas)} new tool ideas below."
        ),
        action="run_research",
        topic=topic,
        ideas=result.ideas,
        research={
            "sources_count": result.sources_count,
            "queries_run": result.queries_run,
        },
        context_tool_count=tool_count,
    )
