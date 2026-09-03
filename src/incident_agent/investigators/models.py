"""Shared task and evidence contracts for bounded investigations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, Self
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal["metric", "log", "trace", "change"]
EvidenceSourceType = Literal["metric", "log", "trace", "change", "deployment", "k8s"]


class TimeWindow(BaseModel):
    """A bounded, timezone-aware half-open investigation window."""

    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("window timestamps must include timezone")
        if self.end <= self.start:
            raise ValueError("window end must be after start")
        if self.end - self.start > timedelta(minutes=30):
            raise ValueError("window cannot exceed 30 minutes")
        return self


class InvestigationTask(BaseModel):
    """A structured task accepted by an investigator."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    source_type: SourceType
    service: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    template_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    parameters: dict[str, str | int | float] = Field(
        default_factory=dict, max_length=16
    )
    window: TimeWindow
    hypothesis_ids: list[UUID] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_parameters(self) -> Self:
        # The union of keys used by registered templates. Source-specific
        # validation is performed by each investigator before querying.
        allowed = {
            "aggregation",
            "group_by",
            "operation",
            "status",
            "limit",
            "max_lines",
            "namespace",
            "environment",
            "version",
            "component",
        }
        unknown = set(self.parameters) - allowed
        if unknown:
            raise ValueError(f"unknown investigation parameter: {sorted(unknown)[0]}")
        for key in ("limit", "max_lines"):
            value = self.parameters.get(key)
            if value is not None and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 1 <= value <= 100
            ):
                raise ValueError(f"{key} must be an integer between 1 and 100")
        return self


_EVIDENCE_NAMESPACE = UUID("a4f0be2a-58f0-4f31-a3cc-66d62dd2cc4b")


class Evidence(BaseModel):
    """Normalized, source-independent observation returned by investigators."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID | None = None
    source_type: EvidenceSourceType
    source_ref: str = Field(min_length=1, max_length=2048)
    observed_at: datetime
    window_start: datetime
    window_end: datetime
    query_template_id: str = Field(min_length=1, max_length=128)
    rendered_query_hash: str = Field(min_length=1, max_length=128)
    statement: str = Field(min_length=1, max_length=4096)
    supports: list[str] = Field(default_factory=list, max_length=32)
    contradicts: list[str] = Field(default_factory=list, max_length=32)
    confidence: float = Field(ge=0, le=1)
    missing_source: bool = False
    missing_reason: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        for value in (self.observed_at, self.window_start, self.window_end):
            if value.tzinfo is None:
                raise ValueError("evidence timestamps must include timezone")
        if self.window_end <= self.window_start:
            raise ValueError("evidence window end must be after start")
        if self.window_end - self.window_start > timedelta(minutes=30):
            raise ValueError("evidence window cannot exceed 30 minutes")
        if self.missing_source and self.confidence != 0:
            raise ValueError("missing-source evidence must have zero confidence")
        if self.missing_source and not self.missing_reason:
            raise ValueError("missing-source evidence requires a reason")
        canonical = {
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "observed_at": self.observed_at.astimezone(UTC).isoformat(),
            "window_start": self.window_start.astimezone(UTC).isoformat(),
            "window_end": self.window_end.astimezone(UTC).isoformat(),
            "query_template_id": self.query_template_id,
            "rendered_query_hash": self.rendered_query_hash,
            "statement": self.statement,
            "supports": sorted(self.supports),
            "contradicts": sorted(self.contradicts),
            "missing_source": self.missing_source,
            "missing_reason": self.missing_reason,
        }
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        object.__setattr__(self, "evidence_id", uuid5(_EVIDENCE_NAMESPACE, digest))
        return self

    @classmethod
    def missing(
        cls,
        *,
        source_type: EvidenceSourceType,
        observed_at: datetime,
        window_start: datetime,
        window_end: datetime,
        query_template_id: str,
        reason: str,
    ) -> Evidence:
        return cls(
            source_type=source_type,
            source_ref=f"missing://{source_type}",
            observed_at=observed_at,
            window_start=window_start,
            window_end=window_end,
            query_template_id=query_template_id,
            rendered_query_hash="missing-source",
            statement=f"missing-source: {reason}",
            confidence=0,
            missing_source=True,
            missing_reason=reason,
        )


def merge_evidence_by_id(
    existing: list[Evidence], incoming: list[Evidence]
) -> list[Evidence]:
    """Merge parallel/retried investigator results without duplicate IDs."""

    merged = list(existing)
    known = {item.evidence_id for item in merged}
    for item in incoming:
        if item.evidence_id not in known:
            merged.append(item)
            known.add(item.evidence_id)
    return merged
