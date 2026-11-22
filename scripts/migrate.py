"""Print the migration SQL that must be applied in Supabase.

Supabase's Python client does not execute arbitrary DDL, so migrations are
shipped as a SQL file for the dashboard / CLI. This helper locates and prints
it so deployment scripts stay simple.
"""

from __future__ import annotations

from pathlib import Path


def migration_path() -> Path:
    """Return the research-inbox migration SQL path."""
    return (
        Path(__file__).resolve().parents[1]
        / "database"
        / "003_cleanup_and_ideas.sql"
    )


def main() -> None:
    """Print migration SQL and application instructions."""
    path = migration_path()
    print("-- Apply this file in the Supabase SQL editor or via the Supabase CLI:")
    print(f"--   {path}")
    print()
    print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
