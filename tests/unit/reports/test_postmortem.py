from incident_agent.reports.postmortem import render_postmortem


def test_postmortem_separates_facts_inferences_and_actions():
    report = render_postmortem(
        incident={"id": "i-1", "service": "orders", "status": "resolved"},
        facts=["error rate returned below threshold"],
        inferences=["deployment introduced slow query"],
        actions=["keep index migration tracked"],
    )
    assert "## 事实" in report
    assert "## 推断" in report
    assert "## 后续行动" in report
