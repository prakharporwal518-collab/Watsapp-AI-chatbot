"""Application settings, loaded from environment variables (or a local .env file).

Every secret comes from the environment. Nothing sensitive is hardcoded.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General -----------------------------------------------------------------
    app_name: str = "WhatsApp AI Tutor"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = False
    default_timezone: str = "Asia/Kolkata"

    # --- Database / cache --------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./tutor.db"
    auto_create_tables: bool = True  # dev convenience; use Alembic migrations in production
    seed_on_startup: bool = True
    redis_url: str | None = None

    # --- WhatsApp Cloud API ------------------------------------------------------
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v25.0"
    whatsapp_api_base_url: str = "https://graph.facebook.com"
    whatsapp_reminder_template: str = ""  # approved template name used outside the 24h window
    whatsapp_template_language: str = "en"
    allow_unsigned_webhooks: bool = False  # NEVER enable in production

    # --- LLM ---------------------------------------------------------------------
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    llm_timeout_seconds: float = 60.0
    llm_daily_limit_per_user: int = 150

    # --- Security & privacy ------------------------------------------------------
    data_encryption_key: str = ""  # Fernet key, see README
    identifier_hash_secret: str = ""  # HMAC pepper used to hash WhatsApp IDs
    internal_api_token: str = ""  # bearer token protecting /internal/* job endpoints
    history_retention_days: int = 30
    history_max_messages_per_user: int = 60

    # --- Behaviour ---------------------------------------------------------------
    rate_limit_per_minute: int = 20
    max_message_chars: int = 1500
    max_chunks_per_reply: int = 5
    default_quiz_size: int = 5
    max_quiz_size: int = 15
    enable_scheduler: bool = False  # in-process reminders (alternative: n8n / cron hitting /internal/jobs)
    dev_chat_enabled: bool = True  # /dev/chat endpoint for local testing (disabled in production)

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Render/Railway/Heroku hand out postgres:// URLs; SQLAlchemy async needs the driver name.
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.environment == "production":
            missing = [
                name
                for name in (
                    "whatsapp_access_token",
                    "whatsapp_phone_number_id",
                    "whatsapp_verify_token",
                    "whatsapp_app_secret",
                    "data_encryption_key",
                    "identifier_hash_secret",
                    "internal_api_token",
                )
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing).upper()}")
            if self.allow_unsigned_webhooks:
                raise ValueError("ALLOW_UNSIGNED_WEBHOOKS must be false in production")
            self.dev_chat_enabled = False
        return self

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_access_token and self.whatsapp_phone_number_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
