from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from incident_agent.investigators.changes import FakeChangesInvestigator
from incident_agent.investigators.logs import FakeLogsInvestigator
from incident_agent.investigators.metrics import FakeMetricsInvestigator
from incident_agent.investigators.models import InvestigationTask
from incident_agent.investigators.traces import FakeTracesInvestigator


def _task(
    source: str, template: str, parameters: dict[str, str | int | float] | None = None
):
    end = datetime.now(UTC)
    return InvestigationTask(
        task_id=uuid4(),
        source_type=source,
        service="orders",
        template_id=template,
        parameters=parameters or {},
        window={"start": end - timedelta(minutes=5), "end": end},
        hypothesis_ids=[],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("investigator", "task"),
    [
        (FakeMetricsInvestigator(), _task("metric", "service_error_rate")),
        (FakeLogsInvestigator(), _task("log", "error_signature_count")),
        (FakeTracesInvestigator(), _task("trace", "error_trace_search")),
        (FakeChangesInvestigator(), _task("change", "recent_deployments")),
    ],
)
async def test_fake_investigators_return_normalized_evidence(investigator, task):
    evidence = await investigator.investigate(task)
    assert evidence
    assert all(item.source_type == task.source_type for item in evidence)
    assert all(item.window_end <= task.window.end for item in evidence)


@pytest.mark.asyncio
async def test_unavailable_source_returns_missing_source_evidence():
    task = _task("trace", "error_trace_search")
    evidence = await FakeTracesInvestigator(available=False).investigate(task)
    assert len(evidence) == 1
    assert evidence[0].missing_source is True
    assert evidence[0].source_type == "trace"


@pytest.mark.asyncio
async def test_fake_investigator_rejects_template_from_another_source():
    task = _task("metric", "error_signature_count")
    with pytest.raises(ValueError, match="template"):
        await FakeMetricsInvestigator().investigate(task)
