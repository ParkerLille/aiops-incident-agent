"""Contracts used by the runbook registry, policy and executor."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _DeploymentParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(
        min_length=1, max_length=63, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"
    )
    deployment: str = Field(
        min_length=1, max_length=63, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"
    )


class RestartDeploymentParameters(_DeploymentParameters):
    grace_period_seconds: int = Field(default=30, ge=0, le=300)


class ScaleDeploymentParameters(_DeploymentParameters):
    replicas: int = Field(ge=1, le=100)


class RollbackDeploymentParameters(_DeploymentParameters):
    revision: int = Field(ge=1, le=100_000)


RunbookName = Literal["restart_deployment", "scale_deployment", "rollback_deployment"]


class RunbookExecutionCommand(BaseModel):
    """A typed command accepted by an isolated executor, never natural language."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    runbook_name: RunbookName
    runbook_version: str = Field(min_length=1, max_length=32)
    environment: str = Field(
        min_length=1, max_length=32, pattern=r"^[a-z0-9][a-z0-9-]*$"
    )
    parameters: dict[str, str | int] = Field(min_length=2, max_length=16)
    target_resource_uid: str = Field(min_length=1, max_length=256)
    approval_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=256)
    expected_resource_version: str | None = Field(default=None, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value

    def request_hash(self) -> str:
        # The expected resource version is a precondition observed at execution
        # time; it is intentionally excluded so adding that guard does not
        # invalidate a human approval for the same action.
        payload = self.model_dump(
            mode="json", exclude={"approval_id", "expected_resource_version"}
        )
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Approval(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    request_hash: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    reason: str | None = None


class ExecutionResult(BaseModel):
    execution_id: UUID = Field(default_factory=uuid4)
    idempotency_key: str
    runbook_name: RunbookName
    status: Literal["executed", "failed"] = "executed"
    replayed: bool = False
    before_resource_version: str | None = None
    after_resource_version: str | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
