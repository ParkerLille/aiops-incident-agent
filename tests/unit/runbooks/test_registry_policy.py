from uuid import uuid4

import pytest

from incident_agent.runbooks.models import RunbookExecutionCommand
from incident_agent.runbooks.policy import RunbookPolicy
from incident_agent.runbooks.registry import RunbookRegistry, default_registry


def _command(name: str, *, environment: str = "lab", namespace: str = "lab"):
    values: dict[str, str | int] = {"namespace": namespace, "deployment": "orders"}
    if name == "scale_deployment":
        values["replicas"] = 3
    if name == "rollback_deployment":
        values["revision"] = 7
    return RunbookExecutionCommand(
        incident_id=uuid4(),
        runbook_name=name,
        runbook_version="1.0.0",
        environment=environment,
        parameters=values,
        target_resource_uid="uid-1",
        idempotency_key=f"{name}-key",
    )


def test_default_registry_contains_three_versioned_runbooks():
    registry = default_registry()
    assert {item.name for item in registry.list()} == {
        "restart_deployment",
        "scale_deployment",
        "rollback_deployment",
    }
    assert registry.get("restart_deployment", "1.0.0").risk_level == "low"


def test_registry_rejects_duplicate_version():
    registry = RunbookRegistry()
    registry.register(default_registry().get("restart_deployment", "1.0.0"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(default_registry().get("restart_deployment", "1.0.0"))


def test_lab_restart_is_automatic_but_scale_requires_approval():
    policy = RunbookPolicy(default_registry())
    restart = policy.evaluate(_command("restart_deployment"))
    scale = policy.evaluate(_command("scale_deployment"))
    assert restart.allowed is True
    assert restart.requires_approval is False
    assert scale.allowed is True
    assert scale.requires_approval is True


def test_production_and_namespace_escape_are_denied_or_approval_required():
    policy = RunbookPolicy(default_registry(), allowed_namespaces={"lab"})
    production = policy.evaluate(
        _command("restart_deployment", environment="production", namespace="lab")
    )
    escaped = policy.evaluate(_command("restart_deployment", namespace="kube-system"))
    assert production.requires_approval is True
    assert escaped.allowed is False
    assert escaped.reason_code == "namespace_not_allowed"
