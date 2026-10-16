from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # repo root (Megamind/)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = ROOT / "data"
    frontend_dist: Path = ROOT / "frontend" / "dist"

    # Admin access (single owner)
    admin_password: str = "change-me"
    secret_key: str = "dev-only-secret-change-me"

    # LLM: "ollama" (local, default) or "anthropic" (any Anthropic Messages-compatible API)
    llm_provider: str = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen3:8b"
    embed_model: str = "bge-m3"
    num_ctx: int = 8192
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    # Owner / notifications
    timezone: str = "Africa/Cairo"
    whatsapp_phone: str = ""          # international format, e.g. +2010xxxxxxxx
    callmebot_apikey: str = ""
    daily_briefing_time: str = "08:00"

    # Google Calendar (OAuth "Web application" client)
    public_base_url: str = "http://localhost:8000"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "megamind.db"

    @property
    def google_dir(self) -> Path:
        return self.data_dir / "google"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    for sub in ("", "sources", "uploads", "pdf", "book", "cv", "google", "translated", "translation", "tmp", "notes",
                "book_src"):
        (s.data_dir / sub).mkdir(parents=True, exist_ok=True)
    return s
