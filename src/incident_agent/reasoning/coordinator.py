"""Parallel investigator coordinator with evidence de-duplication."""

import asyncio
from collections.abc import Mapping

from incident_agent.investigators.base import Investigator
from incident_agent.investigators.models import (
    Evidence,
    InvestigationTask,
    merge_evidence_by_id,
)


class InvestigationCoordinator:
    def __init__(self, investigators: Mapping[str, Investigator]):
        self.investigators = investigators

    async def investigate(self, tasks: list[InvestigationTask]) -> list[Evidence]:
        async def run(task: InvestigationTask) -> list[Evidence]:
            investigator = self.investigators.get(task.source_type)
            if investigator is None:
                return [
                    Evidence.missing(
                        source_type=task.source_type,
                        observed_at=task.window.end,
                        window_start=task.window.start,
                        window_end=task.window.end,
                        query_template_id=task.template_id,
                        reason=f"investigator unavailable: {task.source_type}",
                    )
                ]
            try:
                return await investigator.investigate(task)
            except Exception as exc:
                return [
                    Evidence.missing(
                        source_type=task.source_type,
                        observed_at=task.window.end,
                        window_start=task.window.start,
                        window_end=task.window.end,
                        query_template_id=task.template_id,
                        reason=str(exc),
                    )
                ]

        batches = await asyncio.gather(*(run(task) for task in tasks))
        evidence: list[Evidence] = []
        for batch in batches:
            evidence = merge_evidence_by_id(evidence, batch)
        return evidence
