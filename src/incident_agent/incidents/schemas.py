"""Validated, size-limited Alertmanager webhook models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertmanagerAlert(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    labels: dict[str, str] = Field(min_length=3, max_length=32)
    annotations: dict[str, str] = Field(default_factory=dict, max_length=32)
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime | None = Field(default=None, alias="endsAt")
    generator_url: str | None = Field(default=None, alias="generatorURL")

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, labels: dict[str, str]) -> dict[str, str]:
        required = {"alertname", "service", "environment"}
        if not required.issubset(labels):
            missing = ", ".join(sorted(required - labels.keys()))
            raise ValueError(f"missing required labels: {missing}")
        if any(len(key) > 128 or len(value) > 256 for key, value in labels.items()):
            raise ValueError("label key or value exceeds length limit")
        return labels

    @field_validator("annotations")
    @classmethod
    def validate_annotations(cls, annotations: dict[str, str]) -> dict[str, str]:
        if any(
            len(key) > 128 or len(value) > 2048 for key, value in annotations.items()
        ):
            raise ValueError("annotation key or value exceeds length limit")
        return annotations


class AlertmanagerWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore")

    alerts: list[AlertmanagerAlert] = Field(min_length=1, max_length=100)
    status: str | None = None
    receiver: str | None = None
    external_url: str | None = Field(default=None, alias="externalURL")


class IncidentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    environment: str
    service: str
    severity: str
    status: str
    first_seen: datetime
    last_seen: datetime
    version: int
    alerts: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
