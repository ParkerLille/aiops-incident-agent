"""Deterministic fake traces investigator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import observation_time, rendered_hash, validate_task
from .models import Evidence, InvestigationTask

TRACE_TEMPLATES = {
    "error_trace_search": frozenset({"operation", "status"}),
    "span_latency_breakdown": frozenset({"operation"}),
    "dependency_propagation": frozenset({"operation"}),
    "error_traces": frozenset({"operation", "status"}),
    "span_latency": frozenset({"operation"}),
}


class FakeTracesInvestigator:
    def __init__(
        self, observations: Mapping[str, Any] | None = None, *, available: bool = True
    ):
        self.observations = observations or {}
        self.available = available

    async def investigate(self, task: InvestigationTask) -> list[Evidence]:
        validate_task(task, source_type="trace", templates=TRACE_TEMPLATES)
        if not self.available:
            return [
                Evidence.missing(
                    source_type="trace",
                    observed_at=task.window.end,
                    window_start=task.window.start,
                    window_end=task.window.end,
                    query_template_id=task.template_id,
                    reason="traces source unavailable",
                )
            ]
        value = self.observations.get(task.template_id, 0)
        return [
            Evidence(
                source_type="trace",
                source_ref=f"tempo://{task.service}/{task.template_id}",
                observed_at=observation_time(task),
                window_start=task.window.start,
                window_end=task.window.end,
                query_template_id=task.template_id,
                rendered_query_hash=rendered_hash(task),
                statement=f"{task.template_id} for {task.service}: {value}",
                supports=[f"trace:{task.template_id}"],
                confidence=0.78,
            )
        ]


FakeTraceInvestigator = FakeTracesInvestigator
