"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with safe development defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AIOPS_",
        extra="ignore",
    )

    environment: Literal["test", "development", "production"] = "development"
    database_url: str | None = None
    redis_url: str | None = None
    alertmanager_webhook_secret: str | None = None
    require_webhook_signature: bool = False
    max_alert_payload_bytes: int = Field(
        default=1_048_576,
        gt=0,
        le=10_485_760,
    )

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if self.environment == "test" and self.database_url is None:
            self.database_url = "sqlite:///:memory:"
        elif self.environment == "development" and self.database_url is None:
            self.database_url = "sqlite:///./incident-agent.db"

        if self.environment == "production":
            missing = [
                name
                for name, value in (
                    ("database_url", self.database_url),
                    ("redis_url", self.redis_url),
                    ("alertmanager_webhook_secret", self.alertmanager_webhook_secret),
                )
                if not value
            ]
            if missing:
                raise ValueError("production requires " + ", ".join(missing))
            self.require_webhook_signature = True

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""

    return Settings()
