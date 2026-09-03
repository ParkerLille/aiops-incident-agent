"""Deterministic graders for RCA candidate outputs."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RootCauseGrade:
    top1: bool
    top3: bool
    traceability: float


def grade_root_cause(
    candidates: list[dict[str, Any]], ground_truth: str, evidence_ids: Iterable[str]
) -> RootCauseGrade:
    candidate_summaries = [str(item.get("summary", "")) for item in candidates]
    known = set(evidence_ids)
    referenced = {
        str(evidence_id)
        for item in candidates[:3]
        for evidence_id in item.get("evidence_ids", [])
    }
    traceability = len(referenced & known) / len(referenced) if referenced else 0.0
    return RootCauseGrade(
        top1=bool(candidate_summaries and candidate_summaries[0] == ground_truth),
        top3=ground_truth in candidate_summaries[:3],
        traceability=traceability,
    )
