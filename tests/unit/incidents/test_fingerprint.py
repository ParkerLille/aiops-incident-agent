from incident_agent.incidents.fingerprint import compute_fingerprint


def test_fingerprint_ignores_label_order_and_dynamic_fields():
    first = compute_fingerprint(
        {
            "service": "orders",
            "environment": "lab",
            "alertname": "HighP95",
            "startsAt": "one",
        }
    )
    second = compute_fingerprint(
        {
            "alertname": "HighP95",
            "environment": "lab",
            "service": "orders",
            "startsAt": "two",
        }
    )
    assert first == second


def test_fingerprint_changes_for_core_label():
    assert compute_fingerprint(
        {"service": "orders", "environment": "lab", "alertname": "HighP95"}
    ) != compute_fingerprint(
        {"service": "payments", "environment": "lab", "alertname": "HighP95"}
    )
