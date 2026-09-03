"""Versioned registry of the small, type-safe runbook set."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    RestartDeploymentParameters,
    RollbackDeploymentParameters,
    RunbookName,
    ScaleDeploymentParameters,
)

ParameterModel = TypeVar("ParameterModel", bound=type[BaseModel])


class RunbookDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: RunbookName
    version: str = Field(min_length=1, max_length=32)
    parameter_model: type[BaseModel]
    allowed_environments: frozenset[str] = frozenset(
        {"lab", "development", "production"}
    )
    risk_level: str = Field(pattern=r"^(low|medium|high)$")
    requires_approval: bool
    timeout_seconds: int = Field(ge=1, le=3600)
    verification_policy: str = Field(min_length=1, max_length=128)

    @property
    def parameter_schema(self) -> dict[str, object]:
        """Expose the public JSON schema for UI and dry-run consumers."""
        return self.parameter_model.model_json_schema()


class RunbookRegistry:
    def __init__(self, definitions: Iterable[RunbookDefinition] = ()) -> None:
        self._definitions: dict[tuple[str, str], RunbookDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: RunbookDefinition) -> None:
        key = (definition.name, definition.version)
        if key in self._definitions:
            raise ValueError(
                f"runbook {definition.name}@{definition.version} already registered"
            )
        self._definitions[key] = definition

    def get(self, name: str, version: str) -> RunbookDefinition:
        try:
            return self._definitions[(name, version)]
        except KeyError as exc:
            raise ValueError(f"runbook is not registered: {name}@{version}") from exc

    def list(self) -> list[RunbookDefinition]:
        return list(self._definitions.values())

    def validate_parameters(
        self, name: str, version: str, parameters: dict[str, str | int]
    ) -> BaseModel:
        definition = self.get(name, version)
        return definition.parameter_model.model_validate(parameters)


def default_registry() -> RunbookRegistry:
    return RunbookRegistry(
        [
            RunbookDefinition(
                name="restart_deployment",
                version="1.0.0",
                parameter_model=RestartDeploymentParameters,
                risk_level="low",
                requires_approval=False,
                timeout_seconds=300,
                verification_policy="deployment_available",
            ),
            RunbookDefinition(
                name="scale_deployment",
                version="1.0.0",
                parameter_model=ScaleDeploymentParameters,
                risk_level="medium",
                requires_approval=True,
                timeout_seconds=300,
                verification_policy="replicas_available",
            ),
            RunbookDefinition(
                name="rollback_deployment",
                version="1.0.0",
                parameter_model=RollbackDeploymentParameters,
                risk_level="high",
                requires_approval=True,
                timeout_seconds=600,
                verification_policy="deployment_available",
            ),
        ]
    )
