"""Typed application settings loaded from the environment / .env file."""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CORS_ORIGINS = [
    "https://toolpika.vercel.app",
    "http://localhost:3000",
    "https://toolpika.site",
]

REQUIRED_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "TAVILY_API_KEY",
    "NVIDIA_NIM_API_KEY",
    "GROQ_API_KEY",
)


class Settings(BaseSettings):
    """All service settings, resolved from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    tavily_api_key: str = ""
    nvidia_nim_api_key: str = ""
    groq_api_key: str = ""

    qstash_url: str = "https://qstash.upstash.io"
    qstash_token: str = ""

    app_env: str = "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    frontend_url: str = "https://toolpika.vercel.app"

    cron_research_enabled: bool = True
    cron_research_schedule: str = "0 3 * * *"

    qa_max_retries: int = 3
    translation_delay_minutes: int = 5
    translation_call_delay_seconds: float = 1.0
    default_locales: str = "de,fr,es,it,pt-BR,ru,tr,ar,hi"

    nemotron_endpoint: str = "https://integrate.api.nvidia.com/v1/chat/completions"
    nemotron_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    groq_model: str = "llama-3.3-70b-versatile"

    # Tool Studio (admin chat + code generation)
    studio_enabled: bool = True
    studio_frontend_path: str = ""
    studio_context_specs: int = 5
    studio_run_typecheck: bool = False
    studio_codegen_model: str = ""
    studio_max_code_chars: int = 20000

    # GitHub PR publishing for the Studio apply step
    github_pat: str = ""
    github_repo_owner: str = ""
    github_repo_name: str = ""
    github_base_branch: str = "main"
    studio_auto_merge_pr: bool = False

    template_path: str = ""

    @property
    def locales(self) -> list[str]:
        """Return the configured target locales as a clean list."""
        return [item.strip() for item in self.default_locales.split(",") if item.strip()]

    @property
    def is_test(self) -> bool:
        """Whether settings are running under the test suite."""
        return self.app_env.lower() in {"test", "testing", "ci"}

    def validate_required(self) -> None:
        """Raise when a required provider key is missing in production.

        Tests run with APP_ENV=test so they never need real credentials.
        """
        if self.is_test:
            return
        missing = [
            key for key in REQUIRED_KEYS if not str(getattr(self, key.lower(), ""))
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )

    def public_config(self) -> dict[str, Any]:
        """Safe subset exposed to the frontend via /api/config."""
        return {
            "pipeline_enabled": True,
            "available_locales": self.locales,
            "max_retries": self.qa_max_retries,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()


settings = get_settings()
