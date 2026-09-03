from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from incident_agent.runbooks.approval import ApprovalService
from incident_agent.runbooks.executor import FakeRunbookExecutor
from incident_agent.runbooks.models import RunbookExecutionCommand
from incident_agent.runbooks.policy import RunbookPolicy
from incident_agent.runbooks.registry import default_registry


def _command(key: str = "same-key", uid: str = "uid-1"):
    return RunbookExecutionCommand(
        incident_id=uuid4(),
        runbook_name="scale_deployment",
        runbook_version="1.0.0",
        environment="lab",
        parameters={"namespace": "lab", "deployment": "orders", "replicas": 3},
        target_resource_uid=uid,
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_approval_expiry_and_decision_state_machine():
    service = ApprovalService(ttl=timedelta(seconds=1))
    approval = service.request(_command())
    assert approval.status.value == "pending"
    approved = service.decide(approval.id, approved=True, actor="oncall")
    assert approved.status.value == "approved"
    assert service.decide(approval.id, approved=True, actor="oncall").id == approved.id
    with pytest.raises(ValueError, match="cannot transition"):
        service.decide(approval.id, approved=False, actor="oncall")


@pytest.mark.asyncio
async def test_fake_executor_is_idempotent_for_same_command():
    policy = RunbookPolicy(default_registry())
    approvals = ApprovalService()
    executor = FakeRunbookExecutor(policy, approvals)
    command = _command()
    approval = approvals.request(command)
    approvals.decide(approval.id, approved=True, actor="approver")
    command = command.model_copy(update={"approval_id": approval.id})
    first = await executor.execute(command)
    second = await executor.execute(command)
    assert first.execution_id == second.execution_id
    assert first.replayed is False
    assert second.replayed is True
    assert len(executor.executions) == 1


@pytest.mark.asyncio
async def test_fake_executor_rejects_uid_change_and_reuses_key_conflict():
    policy = RunbookPolicy(default_registry())
    approvals = ApprovalService()
    executor = FakeRunbookExecutor(policy, approvals, resources={"uid-1": "v1"})
    command = _command()
    approval = approvals.request(command)
    approvals.decide(approval.id, approved=True, actor="approver")
    command = command.model_copy(
        update={"approval_id": approval.id, "expected_resource_version": "v1"}
    )
    await executor.execute(command)
    with pytest.raises(ValueError, match="idempotency key conflict"):
        await executor.execute(
            command.model_copy(update={"target_resource_uid": "uid-2"})
        )


def test_expired_approval_is_not_valid():
    clock = [datetime.now(UTC)]
    service = ApprovalService(now=lambda: clock[0])
    approval = service.request(_command())
    clock[0] = approval.expires_at + timedelta(seconds=1)
    assert service.get(approval.id).status.value == "expired"
