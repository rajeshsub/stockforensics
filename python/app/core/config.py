"""Application configuration via pydantic-settings (reads .env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets default empty so offline bootstrap works (Q7)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SEC (required header, not secret)
    sec_user_agent: str = "StockForensics research <you@example.com>"

    # Universe / sizing
    top_n: int = 10
    universe_auto_refresh: bool = True
    universe_ttl_hours: int = 24

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_rpm: int = 10

    # Access control (gatekeeping for hosted deployments)
    api_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index: str = "stockforensics"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Live market-data polling on the detail view (Q5)
    poll_interval_s: int = 10
    poll_max: int = 60  # 60 * 10s = 10 min cap per stock

    # Cache / storage
    prompt_version: int = 1
    sqlite_path: str = "data/stockforensics.db"
    log_level: str = "INFO"
    log_json: bool = True

    @property
    def top_n_clamped(self) -> int:
        """TOP_N bounded to [1, 100] per plan."""
        return max(1, min(self.top_n, 100))

    def has(self, key: str) -> bool:
        """True if a named secret is present (non-empty)."""
        return bool(getattr(self, key, "") or "")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
