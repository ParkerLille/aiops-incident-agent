from uuid import uuid4

import pytest

from incident_agent.runbooks.approval import ApprovalService
from incident_agent.runbooks.executor import FakeRunbookExecutor
from incident_agent.runbooks.models import RunbookExecutionCommand
from incident_agent.runbooks.policy import RunbookPolicy
from incident_agent.runbooks.registry import default_registry


def _scale_command(key: str = "incident-1/scale") -> RunbookExecutionCommand:
    return RunbookExecutionCommand(
        incident_id=uuid4(),
        runbook_name="scale_deployment",
        runbook_version="1.0.0",
        environment="lab",
        parameters={"namespace": "lab", "deployment": "orders", "replicas": 4},
        target_resource_uid="deployment/orders",
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_scale_requires_approval_then_executes_once():
    approvals = ApprovalService()
    executor = FakeRunbookExecutor(RunbookPolicy(default_registry()), approvals)
    command = _scale_command()

    dry_run = await executor.dry_run(command)
    assert dry_run.allowed is True
    assert dry_run.requires_approval is True
    with pytest.raises(ValueError, match="approval is required"):
        await executor.execute(command)

    approval = approvals.request(command)
    approvals.decide(approval.id, approved=True, actor="approver")
    approved_command = command.model_copy(update={"approval_id": approval.id})
    first = await executor.execute(approved_command)
    replay = await executor.execute(approved_command)
    assert first.status == "executed"
    assert replay.replayed is True
