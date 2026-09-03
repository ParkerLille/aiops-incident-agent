import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from apps.api.main import create_app
from incident_agent.shared.config import Settings


def test_signature_is_required_when_enabled():
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite://",
            alertmanager_webhook_secret="secret",
            require_webhook_signature=True,
        )
    )
    with TestClient(app) as client:
        response = client.post("/v1/alerts/alertmanager", json={"alerts": []})
    assert response.status_code == 401


def test_valid_signature_is_accepted():
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite://",
            alertmanager_webhook_secret="secret",
            require_webhook_signature=True,
        )
    )
    payload = {
        "alerts": [
            {
                "labels": {"alertname": "x", "service": "orders", "environment": "lab"},
                "startsAt": "2026-09-04T00:00:00Z",
            }
        ]
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        b"secret", timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    with TestClient(app) as client:
        response = client.post(
            "/v1/alerts/alertmanager",
            content=raw,
            headers={
                "content-type": "application/json",
                "X-AIOps-Timestamp": timestamp,
                "X-AIOps-Signature": f"v1={digest}",
            },
        )
    assert response.status_code == 202
