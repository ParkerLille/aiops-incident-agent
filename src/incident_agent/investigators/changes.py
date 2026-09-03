"""Deterministic fake deployment/change investigator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import observation_time, rendered_hash, validate_task
from .models import Evidence, InvestigationTask

CHANGE_TEMPLATES = {
    "recent_deployments": frozenset({"environment", "limit"}),
    "config_changes": frozenset({"environment", "limit"}),
    "image_version": frozenset({"environment"}),
    "recent_changes": frozenset({"environment", "limit"}),
    "deployment_timeline": frozenset({"environment", "limit"}),
}


class FakeChangesInvestigator:
    def __init__(
        self, observations: Mapping[str, Any] | None = None, *, available: bool = True
    ):
        self.observations = observations or {}
        self.available = available

    async def investigate(self, task: InvestigationTask) -> list[Evidence]:
        validate_task(task, source_type="change", templates=CHANGE_TEMPLATES)
        if not self.available:
            return [
                Evidence.missing(
                    source_type="change",
                    observed_at=task.window.end,
                    window_start=task.window.start,
                    window_end=task.window.end,
                    query_template_id=task.template_id,
                    reason="change source unavailable",
                )
            ]
        value = self.observations.get(task.template_id, "none")
        return [
            Evidence(
                source_type="change",
                source_ref=f"changes://{task.service}/{task.template_id}",
                observed_at=observation_time(task),
                window_start=task.window.start,
                window_end=task.window.end,
                query_template_id=task.template_id,
                rendered_query_hash=rendered_hash(task),
                statement=f"{task.template_id} for {task.service}: {value}",
                supports=[f"change:{task.template_id}"],
                confidence=0.7,
            )
        ]


FakeChangeInvestigator = FakeChangesInvestigator
