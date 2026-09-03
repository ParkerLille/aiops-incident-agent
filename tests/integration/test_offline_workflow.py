from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from incident_agent.investigators.metrics import FakeMetricsInvestigator
from incident_agent.investigators.models import InvestigationTask
from incident_agent.reasoning.coordinator import InvestigationCoordinator
from incident_agent.runbooks.approval import ApprovalService
from incident_agent.runbooks.executor import FakeRunbookExecutor
from incident_agent.runbooks.models import RunbookExecutionCommand
from incident_agent.runbooks.policy import RunbookPolicy
from incident_agent.runbooks.registry import default_registry
from incident_agent.verification.service import VerificationService


@pytest.mark.asyncio
async def test_offline_workflow_runs_investigation_action_and_verification():
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
    evidence = await coordinator.investigate([task])
    assert evidence[0].confidence > 0

    command = RunbookExecutionCommand(
        incident_id=uuid4(),
        runbook_name="restart_deployment",
        runbook_version="1.0.0",
        environment="lab",
        parameters={"namespace": "lab", "deployment": "orders"},
        target_resource_uid="uid-1",
        idempotency_key="workflow-1",
    )
    approvals = ApprovalService()
    executor = FakeRunbookExecutor(RunbookPolicy(default_registry()), approvals)
    result = await executor.execute(command)
    assert result.status == "executed"
    assert (
        VerificationService()
        .verify(
            {
                "error_rate": 0.01,
                "p95_ms": 120,
                "healthy_replicas": 1,
                "desired_replicas": 1,
            }
        )
        .status
        == "recovered"
    )
