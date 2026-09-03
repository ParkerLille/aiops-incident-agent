from fastapi.testclient import TestClient

from apps.api.main import create_app
from incident_agent.shared.config import Settings


def test_live_and_ready_endpoints():
    app = create_app(settings=Settings(environment="test", database_url="sqlite://"))
    with TestClient(app) as client:
        assert client.get("/live").json() == {"status": "ok"}
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
