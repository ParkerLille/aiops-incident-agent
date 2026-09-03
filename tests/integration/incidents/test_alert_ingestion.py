from fastapi.testclient import TestClient

from apps.api.main import create_app
from incident_agent.shared.config import Settings


def _client() -> TestClient:
    settings = Settings(environment="test", database_url="sqlite://")
    return TestClient(create_app(settings=settings))


def _payload() -> dict:
    return {
        "alerts": [
            {
                "labels": {
                    "alertname": "HighP95",
                    "service": "orders",
                    "environment": "lab",
                    "severity": "critical",
                },
                "annotations": {"summary": "latency high"},
                "startsAt": "2026-09-04T00:00:00Z",
                "generatorURL": "http://prometheus.example/graph",
            }
        ]
    }


def test_duplicate_webhook_reuses_incident():
    with _client() as client:
        first = client.post("/v1/alerts/alertmanager", json=_payload())
        second = client.post("/v1/alerts/alertmanager", json=_payload())
    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["incident_ids"] == first.json()["incident_ids"]
    assert second.json()["duplicate_alerts"] == 1


def test_same_batch_groups_by_environment_and_service():
    payload = _payload()
    payload["alerts"].append(
        {
            **payload["alerts"][0],
            "labels": {**payload["alerts"][0]["labels"], "service": "inventory"},
        }
    )
    with _client() as client:
        response = client.post("/v1/alerts/alertmanager", json=payload)
    assert response.status_code == 202
    assert len(response.json()["incident_ids"]) == 2


def test_incident_query_returns_timeline():
    with _client() as client:
        created = client.post("/v1/alerts/alertmanager", json=_payload()).json()
        response = client.get(f"/v1/incidents/{created['incident_ids'][0]}")
    assert response.status_code == 200
    assert [event["type"] for event in response.json()["timeline"]] == [
        "incident_created",
        "alert_received",
    ]


def test_unknown_incident_returns_problem_details():
    with _client() as client:
        response = client.get("/v1/incidents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
