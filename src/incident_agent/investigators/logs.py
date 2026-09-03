"""Deterministic fake logs investigator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import observation_time, rendered_hash, validate_task
from .models import Evidence, InvestigationTask

LOG_TEMPLATES = {
    "error_signature_count": frozenset({"limit"}),
    "trace_id_sample": frozenset({"limit"}),
    "representative_error_sample": frozenset({"limit", "max_lines"}),
    "error_count": frozenset({"limit"}),
    "representative_errors": frozenset({"limit", "max_lines"}),
}


class FakeLogsInvestigator:
    def __init__(
        self, observations: Mapping[str, Any] | None = None, *, available: bool = True
    ):
        self.observations = observations or {}
        self.available = available

    async def investigate(self, task: InvestigationTask) -> list[Evidence]:
        validate_task(task, source_type="log", templates=LOG_TEMPLATES)
        if not self.available:
            return [
                Evidence.missing(
                    source_type="log",
                    observed_at=task.window.end,
                    window_start=task.window.start,
                    window_end=task.window.end,
                    query_template_id=task.template_id,
                    reason="logs source unavailable",
                )
            ]
        value = self.observations.get(task.template_id, 0)
        statement = (
            f"{task.template_id} for {task.service}: {value} (clustered representative)"
        )
        return [
            Evidence(
                source_type="log",
                source_ref=f"loki://{task.service}/{task.template_id}",
                observed_at=observation_time(task),
                window_start=task.window.start,
                window_end=task.window.end,
                query_template_id=task.template_id,
                rendered_query_hash=rendered_hash(task),
                statement=statement,
                supports=[f"log:{task.template_id}"],
                confidence=0.75,
            )
        ]


FakeLogInvestigator = FakeLogsInvestigator
