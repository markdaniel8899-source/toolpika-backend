"""Persistence for Studio sessions, messages and generated drafts.

Production uses the Supabase tables from ``database/002_studio.sql``. Tests and
local runs without Supabase credentials fall back to an in-memory store so the
studio remains usable and testable offline.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from app.config import settings
from app.services import supabase_client

log = structlog.get_logger(__name__)

_MEMORY: dict[str, Any] = {
    "sessions": {},
    "messages": [],
    "drafts": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def memory_mode() -> bool:
    """Whether the in-memory fallback is active."""
    return (
        settings.is_test
        or not settings.supabase_url
        or not settings.supabase_service_role_key
    )


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def create_session(
    title: str | None = None,
    idea: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Create a studio session."""
    session = {
        "id": str(uuid4()),
        "title": (title or idea or "Untitled tool")[:120],
        "idea": idea,
        "source_url": source_url,
        "stage": "intake",
        "status": "active",
        "context": {},
        "created_at": _now(),
        "updated_at": _now(),
    }
    if memory_mode():
        _MEMORY["sessions"][session["id"]] = session
        return _clone(session)
    saved = supabase_client.upsert("studio_sessions", [session], "id")
    return saved[0] if saved else session


def get_session(session_id: str) -> dict[str, Any] | None:
    """Return one session or None."""
    if memory_mode():
        session = _MEMORY["sessions"].get(session_id)
        return _clone(session) if session else None
    rows = supabase_client.select_where(
        "studio_sessions", "*", id=session_id
    )
    return rows[0] if rows else None


def update_session(session_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
    """Update a session and return the changed row."""
    values = {**values, "updated_at": _now()}
    if memory_mode():
        session = _MEMORY["sessions"].get(session_id)
        if not session:
            return None
        session.update(values)
        return _clone(session)
    rows = supabase_client.update(
        "studio_sessions", values, {"id": session_id}
    )
    return rows[0] if rows else None


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent sessions, newest first."""
    if memory_mode():
        sessions = list(_MEMORY["sessions"].values())
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return _clone(sessions[:limit])
    rows = supabase_client.select("studio_sessions", "*")
    rows.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return rows[:limit]


def add_message(
    session_id: str,
    role: str,
    content: str,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a chat message."""
    message = {
        "id": str(uuid4()),
        "session_id": session_id,
        "role": role,
        "content": content,
        "artifacts": artifacts or {},
        "created_at": _now(),
    }
    if memory_mode():
        _MEMORY["messages"].append(message)
        return _clone(message)
    saved = supabase_client.upsert("studio_messages", [message], "id")
    return saved[0] if saved else message


def list_messages(session_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return messages for a session, oldest first."""
    if memory_mode():
        rows = [
            _clone(item)
            for item in _MEMORY["messages"]
            if item.get("session_id") == session_id
        ]
    else:
        rows = supabase_client.select_where(
            "studio_messages", "*", session_id=session_id
        )
    rows.sort(key=lambda item: item.get("created_at", ""))
    return rows[-limit:]


def save_draft(
    session_id: str,
    slug: str,
    blueprint: dict[str, Any],
    spec: dict[str, Any] | None = None,
    code_files: list[dict[str, Any]] | None = None,
    qa: dict[str, Any] | None = None,
    status: str = "draft",
) -> dict[str, Any]:
    """Create or replace the draft for a session/slug."""
    existing = get_latest_draft(session_id)
    draft = {
        "id": existing["id"] if existing else str(uuid4()),
        "session_id": session_id,
        "slug": slug,
        "blueprint": blueprint,
        "spec": spec,
        "code_files": code_files or [],
        "qa": qa or {},
        "status": status,
        "preview_url": existing.get("preview_url") if existing else None,
        "pr_url": existing.get("pr_url") if existing else None,
        "created_at": existing.get("created_at") if existing else _now(),
        "updated_at": _now(),
    }
    if memory_mode():
        _MEMORY["drafts"][draft["id"]] = draft
        return _clone(draft)
    saved = supabase_client.upsert("tool_drafts", [draft], "id")
    return saved[0] if saved else draft


def get_latest_draft(session_id: str) -> dict[str, Any] | None:
    """Return the newest draft for a session."""
    if memory_mode():
        rows = [
            _clone(item)
            for item in _MEMORY["drafts"].values()
            if item.get("session_id") == session_id
        ]
    else:
        rows = supabase_client.select_where(
            "tool_drafts", "*", session_id=session_id
        )
    if not rows:
        return None
    rows.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return rows[0]


def update_draft(draft_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
    """Update one draft."""
    values = {**values, "updated_at": _now()}
    if memory_mode():
        draft = _MEMORY["drafts"].get(draft_id)
        if not draft:
            return None
        draft.update(values)
        return _clone(draft)
    rows = supabase_client.update("tool_drafts", values, {"id": draft_id})
    return rows[0] if rows else None
