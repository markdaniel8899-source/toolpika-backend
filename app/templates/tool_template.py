"""Canonical ToolSpec model and loader for UNIVERSAL_TOOL_TEMPLATE.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings


def template_path() -> Path:
    """Resolve the template markdown path from config or repository layout."""
    if settings.template_path:
        return Path(settings.template_path)
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "markdown" / "UNIVERSAL_TOOL_TEMPLATE.md",
        Path("/app/markdown/UNIVERSAL_TOOL_TEMPLATE.md"),
        here.parents[3] / "markdown" / "UNIVERSAL_TOOL_TEMPLATE.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_template_markdown() -> str:
    """Read the canonical template text used by generator prompts."""
    return template_path().read_text(encoding="utf-8")


class Seo(BaseModel):
    """Search metadata for a tool page."""

    title: str
    description: str


class Example(BaseModel):
    """A real input/output pair for the tool."""

    input: str
    output: str


class About(BaseModel):
    """Long-form SEO content blocks."""

    whatIs: str
    useCases: list[str] = Field(default_factory=list)
    commonMistakes: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)


class Faq(BaseModel):
    """One fully visible FAQ."""

    question: str
    answer: str


class Trust(BaseModel):
    """Authorship metadata."""

    author: str
    lastUpdated: str


class SchemaToggles(BaseModel):
    """Which structured-data blocks to emit."""

    softwareApplication: bool = True
    faqPage: bool = True
    howTo: bool = True
    breadcrumb: bool = True


class TranslationRules(BaseModel):
    """Instructions carried into the translation pipeline."""

    keep: list[str] = Field(default_factory=list)
    note: str = ""


class ToolSpec(BaseModel):
    """Complete tool page specification following the universal template."""

    model_config = ConfigDict(populate_by_name=True)

    slug: str
    category: str
    tier: int = 1
    indexable: bool = True
    name: str
    shortName: str
    componentId: str

    primaryKeyword: str
    secondaryKeywords: list[str] = Field(default_factory=list)
    searchIntent: str = ""
    peopleAlsoAsk: list[str] = Field(default_factory=list)

    seo: Seo
    h1: str
    directAnswer: str
    howToUse: list[str] = Field(default_factory=list)
    example: list[Example] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    about: About
    faqs: list[Faq] = Field(default_factory=list)
    relatedTools: list[str] = Field(default_factory=list)
    trust: Trust
    schema_: SchemaToggles = Field(
        default_factory=SchemaToggles, alias="schema", serialization_alias="schema"
    )
    translation: TranslationRules = Field(default_factory=TranslationRules)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolSpec":
        """Build a spec from a generator dictionary."""
        return cls.model_validate(payload)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-ready dictionary."""
        return self.model_dump(mode="json", by_alias=True)


class ValidationResult(BaseModel):
    """Structured QA outcome."""

    isValid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_against_template(spec: dict[str, Any]) -> ValidationResult:
    """Validate a raw spec dictionary against the universal template rules."""
    from app.qa.validator import validate_spec

    return validate_spec(spec)
