from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from incident_agent.investigators.models import Evidence, InvestigationTask, TimeWindow


def test_time_window_rejects_longer_than_thirty_minutes():
    start = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TimeWindow(start=start, end=start + timedelta(minutes=31))


def test_investigation_task_rejects_unknown_parameter():
    start = datetime.now(UTC)
    with pytest.raises(ValidationError):
        InvestigationTask(
            task_id=uuid4(),
            source_type="metric",
            service="orders",
            template_id="service_error_rate",
            parameters={"arbitrary_query": "rate(foo)"},
            window={"start": start, "end": start + timedelta(minutes=5)},
            hypothesis_ids=[],
        )


def test_evidence_id_is_deterministic_and_missing_source_is_explicit():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = dict(
        source_type="metric",
        source_ref="prometheus://orders/error_rate",
        observed_at=start,
        window_start=start - timedelta(minutes=5),
        window_end=start,
        query_template_id="service_error_rate",
        rendered_query_hash="abc",
        statement="error rate increased to 0.2",
        supports=["h1"],
        contradicts=[],
        confidence=0.8,
    )
    first = Evidence(**values)
    second = Evidence(**values)
    assert first.evidence_id == second.evidence_id

    missing = Evidence.missing(
        source_type="metric",
        observed_at=start,
        window_start=start - timedelta(minutes=5),
        window_end=start,
        query_template_id="service_error_rate",
        reason="Prometheus disabled",
    )
    assert missing.missing_source is True
    assert missing.confidence == 0
    assert "missing-source" in missing.statement
