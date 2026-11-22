"""Shared pytest setup. Forces test mode before app modules are imported."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
