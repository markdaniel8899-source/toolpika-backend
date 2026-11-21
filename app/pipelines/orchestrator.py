"""Master pipeline coordinator: research → generate → QA → publish → translate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config import settings
from app.pipelines import generator, publisher, research, translator
from app.qa.self_corrector import correct_spec
from app.qa.validator import validate_spec
from app.services import supabase_client
from app.templates.tool_template import ValidationResult

log = structlog.get_logger(__name__)


@dataclass
class PipelineResult:
    """Full outcome of one pipeline run."""

    success: bool
    slug: str | None = None
    stage: str = "research"
    logs: list[str] = field(default_factory=list)
    validation: ValidationResult | None = None


def source_hash(spec: dict[str, Any]) -> str:
    """Compute the stable SHA-256 hash used for idempotency."""
    canonical = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _known_slugs() -> list[str]:
    """Return slugs for relatedTools validation."""
    try:
        return [str(row.get("slug")) for row in publisher.list_tools() if row.get("slug")]
    except Exception as exc:  # noqa: BLE001 - QA should still run
        log.warning("registry_lookup_failed", error=str(exc))
        return []


def _log_run(stage: str, status: str, details: dict[str, Any]) -> None:
    """Persist a pipeline run log row when Supabase is available."""
    try:
        supabase_client.upsert(
            "pipeline_runs",
            [{"stage": stage, "status": status, "details": details}],
            "id",
        )
    except Exception as exc:  # noqa: BLE001 - logging must not break the pipeline
        log.warning("run_log_failed", error=str(exc))


async def run_full_pipeline(tool_slug: str | None = None) -> PipelineResult:
    """Run the entire autonomous tool creation pipeline."""
    result = PipelineResult(success=False)

    try:
        result.logs.append(f"research: {tool_slug or 'autonomous trending scan'}")
        candidates = await research.research_trending_tools(tool_slug)
        if not candidates:
            result.stage = "research"
            result.logs.append("research returned no candidates")
            return result
        candidate = candidates[0]

        result.stage = "generate"
        spec = generator.generate_tool_spec(candidate)
        result.slug = str(spec.get("slug", ""))
        result.logs.append(f"generated spec for {result.slug}")

        result.stage = "qa"
        registry = _known_slugs()
        other_specs: list[dict[str, Any]] = []
        try:
            for row in supabase_client.select("tool_specs", "spec"):
                if row.get("spec") and row["spec"].get("slug") != result.slug:
                    other_specs.append(row["spec"])
        except Exception as exc:  # noqa: BLE001
            log.warning("spec_corpus_lookup_failed", error=str(exc))

        validation = validate_spec(spec, other_specs, registry)
        attempts = 1
        while not validation.isValid and attempts < settings.qa_max_retries:
            result.logs.append(f"qa attempt {attempts} failed: {validation.errors}")
            spec = correct_spec(spec, validation.errors)
            validation = validate_spec(spec, other_specs, registry)
            attempts += 1

        result.validation = validation
        if not validation.isValid:
            result.stage = "qa_failed"
            result.logs.append(f"qa failed after {attempts} attempts")
            if result.slug:
                publisher.mark_status(result.slug, "qa_failed")
            _log_run("qa", "failed", {"slug": result.slug, "errors": validation.errors})
            return result

        result.stage = "publish"
        publisher.publish_spec(spec, source_hash(spec))
        result.logs.append("published to Supabase")

        result.stage = "schedule_translation"
        from app.services.queue import schedule_after

        schedule_after(
            settings.translation_delay_minutes,
            f"translate:{result.slug}",
            translator.translate_tool,
            result.slug,
            None,
            spec,
        )
        result.logs.append(
            f"translation scheduled in {settings.translation_delay_minutes} minutes"
        )
        _log_run("pipeline", "success", {"slug": result.slug, "attempts": attempts})
        result.success = True
        result.stage = "complete"
        return result

    except Exception as exc:  # noqa: BLE001 - top level always returns a result
        result.stage = "error"
        result.logs.append(f"{type(exc).__name__}: {exc}")
        log.error("pipeline_failed", error=str(exc))
        _log_run("pipeline", "error", {"error": str(exc)})
        return result
