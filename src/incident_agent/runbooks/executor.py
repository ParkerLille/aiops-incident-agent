"""Fake isolated executor with resource-version and idempotency safeguards."""

from __future__ import annotations

from collections.abc import Mapping

from .approval import ApprovalService
from .models import ExecutionResult, RunbookExecutionCommand
from .policy import PolicyResult, RunbookPolicy


class FakeRunbookExecutor:
    def __init__(
        self,
        policy: RunbookPolicy,
        approvals: ApprovalService,
        *,
        resources: Mapping[str, str] | None = None,
    ) -> None:
        self.policy = policy
        self.approvals = approvals
        self.resources = dict(resources or {})
        self.executions: dict[str, ExecutionResult] = {}
        self._command_hashes: dict[str, str] = {}

    async def dry_run(self, command: RunbookExecutionCommand) -> PolicyResult:
        return self.policy.evaluate(command)

    async def execute(self, command: RunbookExecutionCommand) -> ExecutionResult:
        policy_result = self.policy.evaluate(command)
        if not policy_result.allowed:
            raise ValueError(f"policy denied: {policy_result.reason_code}")
        command_hash = command.request_hash()
        existing = self.executions.get(command.idempotency_key)
        if existing is not None:
            if self._command_hashes[command.idempotency_key] != command_hash:
                raise ValueError("idempotency key conflict")
            return existing.model_copy(update={"replayed": True})
        if policy_result.requires_approval:
            if command.approval_id is None:
                raise ValueError("approval is required")
            self.approvals.validate_for_execution(command.approval_id, command)
        current_version = self.resources.get(command.target_resource_uid)
        if (
            command.expected_resource_version is not None
            and current_version != command.expected_resource_version
        ):
            raise ValueError("target resource version changed")
        next_version = self._next_version(current_version)
        self.resources[command.target_resource_uid] = next_version
        result = ExecutionResult(
            idempotency_key=command.idempotency_key,
            runbook_name=command.runbook_name,
            before_resource_version=current_version,
            after_resource_version=next_version,
        )
        self.executions[command.idempotency_key] = result
        self._command_hashes[command.idempotency_key] = command_hash
        return result

    @staticmethod
    def _next_version(current: str | None) -> str:
        if current is None:
            return "1"
        try:
            return str(int(current) + 1)
        except ValueError:
            return f"{current}:next"
