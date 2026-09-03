from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from incident_agent.investigators.metrics import FakeMetricsInvestigator
from incident_agent.investigators.models import InvestigationTask
from incident_agent.reasoning.coordinator import InvestigationCoordinator


@pytest.mark.asyncio
async def test_coordinator_merges_parallel_evidence_without_duplicates():
    end = datetime.now(UTC)
    task = InvestigationTask(
        task_id=uuid4(),
        source_type="metric",
        service="orders",
        template_id="service_error_rate",
        parameters={"aggregation": "avg", "group_by": "service"},
        window={"start": end - timedelta(minutes=5), "end": end},
        hypothesis_ids=[],
    )
    coordinator = InvestigationCoordinator(
        {"metric": FakeMetricsInvestigator(observations={"service_error_rate": 0.2})}
    )
    result = await coordinator.investigate([task, task])
    assert len(result) == 1
