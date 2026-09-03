"""Deterministic policy gate for runbook actions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .models import RunbookExecutionCommand
from .registry import RunbookRegistry


class PolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    requires_approval: bool = False
    reason_code: str = "allowed"
    message: str = ""
    runbook_name: str | None = None


class RunbookPolicy:
    def __init__(
        self,
        registry: RunbookRegistry,
        *,
        allowed_namespaces: set[str] | frozenset[str] | None = None,
    ) -> None:
        self.registry = registry
        self.allowed_namespaces = (
            frozenset(allowed_namespaces) if allowed_namespaces is not None else None
        )
        self._reserved_namespaces = frozenset(
            {"kube-system", "kube-public", "kube-node-lease"}
        )

    def evaluate(self, command: RunbookExecutionCommand) -> PolicyResult:
        try:
            definition = self.registry.get(
                command.runbook_name, command.runbook_version
            )
        except ValueError as exc:
            return PolicyResult(
                allowed=False, reason_code="runbook_not_registered", message=str(exc)
            )
        if command.environment not in definition.allowed_environments:
            return PolicyResult(
                allowed=False,
                reason_code="environment_not_allowed",
                message="environment is not allowed",
                runbook_name=definition.name,
            )
        namespace = command.parameters.get("namespace")
        if not isinstance(namespace, str) or (
            namespace in self._reserved_namespaces
            or (
                self.allowed_namespaces is not None
                and namespace not in self.allowed_namespaces
            )
        ):
            return PolicyResult(
                allowed=False,
                reason_code="namespace_not_allowed",
                message="namespace is not allowed",
                runbook_name=definition.name,
            )
        try:
            definition.parameter_model.model_validate(command.parameters)
        except Exception as exc:
            return PolicyResult(
                allowed=False,
                reason_code="invalid_parameters",
                message=str(exc),
                runbook_name=definition.name,
            )
        requires_approval = (
            definition.requires_approval or command.environment == "production"
        )
        return PolicyResult(
            allowed=True,
            requires_approval=requires_approval,
            runbook_name=definition.name,
        )
