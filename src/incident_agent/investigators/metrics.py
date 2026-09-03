"""Deterministic fake metrics investigator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import observation_time, rendered_hash, validate_task
from .models import Evidence, InvestigationTask

METRIC_TEMPLATES = {
    "service_request_rate": frozenset({"aggregation", "group_by"}),
    "service_error_rate": frozenset({"aggregation", "group_by"}),
    "service_p95_latency": frozenset({"aggregation", "group_by"}),
    "container_cpu": frozenset({"aggregation"}),
    "container_memory": frozenset({"aggregation"}),
    "redis_pool": frozenset({"aggregation"}),
    "db_duration": frozenset({"aggregation"}),
    "request_rate": frozenset({"aggregation", "group_by"}),
    "error_rate": frozenset({"aggregation", "group_by"}),
    "p95_latency": frozenset({"aggregation", "group_by"}),
}


class FakeMetricsInvestigator:
    def __init__(
        self, observations: Mapping[str, Any] | None = None, *, available: bool = True
    ):
        self.observations = observations or {}
        self.available = available

    async def investigate(self, task: InvestigationTask) -> list[Evidence]:
        validate_task(task, source_type="metric", templates=METRIC_TEMPLATES)
        if not self.available:
            return [
                Evidence.missing(
                    source_type="metric",
                    observed_at=task.window.end,
                    window_start=task.window.start,
                    window_end=task.window.end,
                    query_template_id=task.template_id,
                    reason="metrics source unavailable",
                )
            ]
        value = self.observations.get(task.template_id, 0)
        statement = f"{task.template_id} for {task.service}: {value}"
        return [
            Evidence(
                source_type="metric",
                source_ref=f"prometheus://{task.service}/{task.template_id}",
                observed_at=observation_time(task),
                window_start=task.window.start,
                window_end=task.window.end,
                query_template_id=task.template_id,
                rendered_query_hash=rendered_hash(task),
                statement=statement,
                supports=[f"metric:{task.template_id}"],
                confidence=0.8,
            )
        ]


FakeMetricInvestigator = FakeMetricsInvestigator
