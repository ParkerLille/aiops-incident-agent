"""Deterministic hypothesis scoring from supporting and contradicting evidence."""

from dataclasses import dataclass

from incident_agent.investigators.models import Evidence


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: str
    summary: str
    affected_component: str
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    is_final: bool = False


def rank_hypotheses(
    hypotheses: list[Hypothesis], evidence: list[Evidence]
) -> list[Hypothesis]:
    ranked: list[Hypothesis] = []
    for hypothesis in hypotheses:
        supporting = [item for item in evidence if hypothesis.id in item.supports]
        contradicting = [item for item in evidence if hypothesis.id in item.contradicts]
        score = min(
            1.0, sum(item.confidence for item in supporting) / max(1, len(supporting))
        )
        score = max(0.0, score - 0.25 * len(contradicting))
        ranked.append(
            Hypothesis(
                id=hypothesis.id,
                summary=hypothesis.summary,
                affected_component=hypothesis.affected_component,
                supporting_evidence_ids=tuple(
                    str(item.evidence_id) for item in supporting
                ),
                contradicting_evidence_ids=tuple(
                    str(item.evidence_id) for item in contradicting
                ),
                confidence=score,
                is_final=bool(supporting) and score >= 0.6,
            )
        )
    return sorted(
        ranked, key=lambda item: (item.is_final, item.confidence), reverse=True
    )
