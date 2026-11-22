"""Publisher status helper tests."""

from __future__ import annotations

from app.pipelines import publisher


def test_mark_status_updates_existing_row(monkeypatch):
    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(
        publisher.supabase_client,
        "update",
        lambda table, values, filters: calls.append((table, values, filters))
        or [{"slug": filters["slug"]}],
    )

    publisher.mark_status("word-counter", "qa_failed")

    assert calls == [
        ("tool_specs", {"status": "qa_failed"}, {"slug": "word-counter"})
    ]


def test_mark_status_persists_failed_spec(monkeypatch):
    upserts: list[tuple[str, list[dict], str]] = []
    monkeypatch.setattr(
        publisher.supabase_client,
        "upsert",
        lambda table, rows, on_conflict: upserts.append((table, rows, on_conflict))
        or rows,
    )

    publisher.mark_status("new-tool", "qa_failed", {"slug": "new-tool"})

    assert upserts[0][0] == "tool_specs"
    assert upserts[0][1][0]["spec"] == {"slug": "new-tool"}
    assert upserts[0][1][0]["status"] == "qa_failed"


def test_mark_status_warns_when_slug_is_missing(monkeypatch):
    monkeypatch.setattr(
        publisher.supabase_client,
        "update",
        lambda table, values, filters: [],
    )

    publisher.mark_status("missing", "qa_failed")
