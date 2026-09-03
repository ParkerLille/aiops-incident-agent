"""In-memory approval state machine suitable for local and unit-test execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from .models import Approval, ApprovalStatus, RunbookExecutionCommand


class ApprovalService:
    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=15),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.ttl = ttl
        self._now = now or (lambda: datetime.now(UTC))
        self._approvals: dict[UUID, Approval] = {}

    def request(self, command: RunbookExecutionCommand) -> Approval:
        requested = self._now().astimezone(UTC)
        approval = Approval(
            request_hash=command.request_hash(),
            requested_at=requested,
            expires_at=requested + self.ttl,
        )
        self._approvals[approval.id] = approval
        return approval

    def get(self, approval_id: UUID) -> Approval:
        try:
            approval = self._approvals[approval_id]
        except KeyError as exc:
            raise ValueError("approval not found") from exc
        if (
            approval.status == ApprovalStatus.PENDING
            and self._now().astimezone(UTC) >= approval.expires_at
        ):
            approval = approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
            self._approvals[approval_id] = approval
        return approval

    def decide(
        self,
        approval_id: UUID,
        *,
        approved: bool,
        actor: str,
        reason: str | None = None,
    ) -> Approval:
        current = self.get(approval_id)
        if current.status != ApprovalStatus.PENDING:
            if (approved and current.status == ApprovalStatus.APPROVED) or (
                not approved and current.status == ApprovalStatus.REJECTED
            ):
                return current
            raise ValueError(f"approval cannot transition from {current.status.value}")
        updated = current.model_copy(
            update={
                "status": ApprovalStatus.APPROVED
                if approved
                else ApprovalStatus.REJECTED,
                "decided_at": self._now().astimezone(UTC),
                "decided_by": actor,
                "reason": reason,
            }
        )
        self._approvals[approval_id] = updated
        return updated

    def validate_for_execution(
        self, approval_id: UUID, command: RunbookExecutionCommand
    ) -> Approval:
        approval = self.get(approval_id)
        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("approval is not approved")
        if approval.request_hash != command.request_hash():
            raise ValueError("approval request does not match command")
        return approval
