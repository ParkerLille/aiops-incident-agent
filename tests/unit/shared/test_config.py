import pytest
from pydantic import ValidationError

from incident_agent.shared.config import Settings


def test_development_settings_use_local_defaults():
    settings = Settings(environment="development")
    assert settings.database_url == "sqlite:///./incident-agent.db"
    assert settings.redis_url is None
    assert settings.require_webhook_signature is False


def test_production_settings_require_database_redis_and_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_payload_limit_is_positive():
    with pytest.raises(ValidationError):
        Settings(environment="test", max_alert_payload_bytes=0)
