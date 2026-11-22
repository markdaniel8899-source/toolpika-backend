"""Static registry of tools that ship with the frontend.

The database is the long-term source of truth, but the first generated tool
needs a non-empty registry for ``relatedTools`` validation. These entries mirror
``frontend/src/lib/tools/registry.ts`` and are merged with published Supabase
rows at runtime.
"""

from __future__ import annotations

from typing import Any

SITE_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "slug": "word-counter",
        "name": "Word Counter",
        "category": "text",
        "description": "Count words, characters, sentences and paragraphs in your text.",
        "inputs": ["text"],
    },
    {
        "slug": "case-converter",
        "name": "Case Converter",
        "category": "text",
        "description": "Convert text to UPPERCASE, lowercase, Title Case or camelCase.",
        "inputs": ["text"],
    },
    {
        "slug": "image-compressor",
        "name": "Image Compressor",
        "category": "image",
        "description": "Compress JPEG and PNG images locally in your browser.",
        "inputs": ["file"],
    },
    {
        "slug": "json-formatter",
        "name": "JSON Formatter",
        "category": "code",
        "description": "Format, validate and minify JSON in your browser.",
        "inputs": ["text"],
    },
    {
        "slug": "unit-converter",
        "name": "Unit Converter",
        "category": "converter",
        "description": "Convert length, weight, temperature and more.",
        "inputs": ["text"],
    },
    {
        "slug": "password-generator",
        "name": "Password Generator",
        "category": "security",
        "description": "Generate strong, random passwords locally.",
        "inputs": [],
    },
    {
        "slug": "url-encoder",
        "name": "URL Encoder / Decoder",
        "category": "converter",
        "description": "Encode or decode URLs and query strings.",
        "inputs": ["text", "url"],
    },
    {
        "slug": "base64-encoder",
        "name": "Base64 Encoder / Decoder",
        "category": "converter",
        "description": "Encode or decode Base64 strings.",
        "inputs": ["text"],
    },
)


def seed_slugs() -> list[str]:
    """Return the slugs of the tools that always exist on the site."""
    return [str(tool["slug"]) for tool in SITE_TOOLS]


def seed_tools() -> list[dict[str, Any]]:
    """Return a copy of the static tool inventory."""
    return [dict(tool) for tool in SITE_TOOLS]
