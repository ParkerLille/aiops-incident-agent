from incident_agent.evals.graders import grade_root_cause


def test_grade_root_cause_reports_top_k_and_traceability():
    result = grade_root_cause(
        candidates=[{"summary": "db slow query", "evidence_ids": ["e1"]}],
        ground_truth="db slow query",
        evidence_ids={"e1"},
    )
    assert result.top1 is True
    assert result.traceability == 1.0
