from fastapi.testclient import TestClient

from apps.api.main import create_app
from incident_agent.incidents.repository import IncidentRepository
from incident_agent.shared.config import Settings
from incident_agent.shared.database import create_engine_and_session
from incident_agent.shared.health import ProbeResult


def test_lab_routes_are_available_in_development():
    app = create_app(
        settings=Settings(environment="development", database_url="sqlite://")
    )
    with TestClient(app) as client:
        response = client.get("/v1/lab/scenarios")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_lab_routes_are_disabled_in_production():
    _, session_factory = create_engine_and_session("sqlite://")
    app = create_app(
        settings=Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost",
            alertmanager_webhook_secret="secret",
        ),
        repository=IncidentRepository(session_factory),
        probes={
            "database": lambda: ProbeResult.ok(),
            "redis": lambda: ProbeResult.disabled(),
        },
    )
    with TestClient(app) as client:
        response = client.get("/v1/lab/scenarios")
    assert response.status_code == 404
