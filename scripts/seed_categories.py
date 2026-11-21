"""Seed the category list into Supabase (mirrors the frontend registry)."""

from __future__ import annotations

from app.services import supabase_client

CATEGORIES = [
    "text",
    "image",
    "file",
    "code",
    "converter",
    "calculator",
    "security",
]


def main() -> None:
    """Upsert canonical categories."""
    rows = [{"slug": slug, "label": slug.title()} for slug in CATEGORIES]
    supabase_client.upsert("categories", rows, "slug")
    print(f"Seeded {len(rows)} categories")


if __name__ == "__main__":
    main()
