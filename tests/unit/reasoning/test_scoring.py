from datetime import UTC, datetime, timedelta

from incident_agent.investigators.models import Evidence
from incident_agent.reasoning.hypotheses import Hypothesis, rank_hypotheses


def _evidence(
    confidence: float, supports: list[str], contradicts: list[str] | None = None
):
    end = datetime.now(UTC)
    return Evidence(
        source_type="metric",
        source_ref="fixture://metric",
        observed_at=end,
        window_start=end - timedelta(minutes=5),
        window_end=end,
        query_template_id="service_error_rate",
        rendered_query_hash="hash",
        statement="fixture observation",
        supports=supports,
        contradicts=contradicts or [],
        confidence=confidence,
    )


def test_rank_requires_supporting_evidence_for_final():
    supported = Hypothesis(
        id="h1", summary="database slow query", affected_component="orders"
    )
    unsupported = Hypothesis(
        id="h2", summary="random cause", affected_component="orders"
    )
    evidence = [_evidence(0.9, ["h1"]), _evidence(0.8, [], ["h2"])]
    ranked = rank_hypotheses([supported, unsupported], evidence)
    assert ranked[0].id == "h1"
    assert ranked[0].is_final is True
    assert ranked[1].is_final is False
