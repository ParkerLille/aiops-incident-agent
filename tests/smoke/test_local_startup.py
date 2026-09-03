from fastapi.testclient import TestClient

from apps.api.main import create_app
from incident_agent.shared.config import Settings


def test_development_defaults_start_without_external_services():
    app = create_app(
        settings=Settings(environment="development", database_url="sqlite://")
    )
    with TestClient(app) as client:
        assert client.get("/live").status_code == 200
        assert client.get("/ready").status_code == 200
