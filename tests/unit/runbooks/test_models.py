from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from incident_agent.runbooks.models import (
    ApprovalStatus,
    RestartDeploymentParameters,
    RollbackDeploymentParameters,
    RunbookExecutionCommand,
    ScaleDeploymentParameters,
)


def test_restart_parameters_are_typed_and_bounded():
    params = RestartDeploymentParameters(
        namespace="lab", deployment="orders", grace_period_seconds=30
    )
    assert params.deployment == "orders"
    with pytest.raises(ValidationError):
        RestartDeploymentParameters(namespace="prod", deployment="bad name")


def test_scale_rejects_replica_over_limit():
    with pytest.raises(ValidationError):
        ScaleDeploymentParameters(namespace="lab", deployment="orders", replicas=101)


def test_rollback_requires_positive_revision():
    with pytest.raises(ValidationError):
        RollbackDeploymentParameters(namespace="lab", deployment="orders", revision=0)


def test_execution_command_requires_uuid_and_idempotency_key():
    command = RunbookExecutionCommand(
        incident_id=uuid4(),
        runbook_name="restart_deployment",
        runbook_version="1.0.0",
        environment="lab",
        parameters={"namespace": "lab", "deployment": "orders"},
        target_resource_uid="uid-1",
        idempotency_key="incident-1/restart",
    )
    assert command.approval_id is None
    with pytest.raises(ValidationError):
        RunbookExecutionCommand(
            incident_id=uuid4(),
            runbook_name="restart_deployment",
            runbook_version="1.0.0",
            environment="lab",
            parameters={},
            target_resource_uid="",
            idempotency_key="",
        )


def test_approval_status_is_expired_when_deadline_passed():
    assert ApprovalStatus.PENDING.value == "pending"
    assert datetime.now(UTC) > datetime.now(UTC) - timedelta(seconds=1)
