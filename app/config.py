"""Typed application settings for the lightweight research-scout backend."""

from __future__ import annotations

from functools import lru_cache

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
)


class Settings(BaseSettings):
    """All service settings, resolved from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    tavily_api_key: str = ""
    nvidia_nim_api_key: str = ""

    app_env: str = "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    frontend_url: str = "https://toolpika.vercel.app"

    # Daily research scout schedule (03:00 UTC by default).
    cron_research_enabled: bool = True
    cron_research_schedule: str = "0 3 * * *"

    nemotron_endpoint: str = "https://integrate.api.nvidia.com/v1/chat/completions"
    nemotron_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"

    @property
    def is_test(self) -> bool:
        """Whether settings are running under the test suite."""
        return self.app_env.lower() in {"test", "testing", "ci"}

    def validate_required(self) -> None:
        """Fail fast in production when a required provider key is missing."""
        if self.is_test:
            return
        missing = [
            key for key in REQUIRED_KEYS if not str(getattr(self, key.lower(), ""))
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()


settings = get_settings()
