"""Investigator protocol and common whitelist enforcement."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from .models import Evidence, InvestigationTask, SourceType


class Investigator(Protocol):
    async def investigate(self, task: InvestigationTask) -> list[Evidence]: ...


def validate_task(
    task: InvestigationTask,
    *,
    source_type: SourceType,
    templates: Mapping[str, frozenset[str]],
) -> str:
    if task.source_type != source_type:
        raise ValueError(f"task source_type must be {source_type}")
    canonical = templates.get(task.template_id)
    if canonical is None:
        raise ValueError(
            f"template is not allowed for {source_type}: {task.template_id}"
        )
    unknown = set(task.parameters) - canonical
    if unknown:
        raise ValueError(f"parameter is not allowed for template: {sorted(unknown)[0]}")
    return task.template_id


def rendered_hash(task: InvestigationTask) -> str:
    payload = {
        "template": task.template_id,
        "service": task.service,
        "parameters": task.parameters,
        "start": task.window.start.astimezone(UTC).isoformat(),
        "end": task.window.end.astimezone(UTC).isoformat(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def observation_time(
    task: InvestigationTask, value: datetime | None = None
) -> datetime:
    return (value or task.window.end).astimezone(UTC)
