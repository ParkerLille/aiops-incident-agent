from incident_agent.lab.scenarios import get_scenario, list_scenarios


def test_three_reproducible_scenarios_have_ground_truth():
    assert len(list_scenarios()) == 3
    assert get_scenario("order_db_slow_query").ground_truth
