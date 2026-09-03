"""Application configuration with safe development defaults."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the incident agent."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AIOPS_", extra="ignore", case_sensitive=False
    )

    environment: Literal["test", "development", "production"] = "development"
    database_url: str = "sqlite:///./incident-agent.db"
    redis_url: str | None = None
    alertmanager_webhook_secret: str | None = None
    require_webhook_signature: bool = False
    max_alert_payload_bytes: int = Field(default=1_048_576, gt=0, le=10_485_760)

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if not self.database_url or self.database_url.startswith("sqlite"):
                raise ValueError("production requires a non-sqlite database_url")
            if not self.redis_url or not self.alertmanager_webhook_secret:
                raise ValueError("production requires redis_url and alertmanager_webhook_secret")
            self.require_webhook_signature = True
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings loaded from the environment."""

    return Settings()
