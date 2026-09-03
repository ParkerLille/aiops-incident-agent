import pytest
from pydantic import ValidationError

from incident_agent.incidents.schemas import AlertmanagerAlert


def test_alert_requires_core_labels_and_starts_at():
    with pytest.raises(ValidationError):
        AlertmanagerAlert(labels={"service": "orders"}, startsAt="2026-09-04T00:00:00Z")
