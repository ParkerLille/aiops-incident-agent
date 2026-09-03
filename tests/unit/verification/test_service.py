from incident_agent.verification.service import VerificationService


def test_recovery_requires_all_signals_for_success():
    service = VerificationService()
    assert (
        service.verify(
            {
                "error_rate": 0.01,
                "p95_ms": 120,
                "healthy_replicas": 3,
                "desired_replicas": 3,
            }
        ).status
        == "recovered"
    )
    assert (
        service.verify(
            {
                "error_rate": 0.2,
                "p95_ms": 120,
                "healthy_replicas": 3,
                "desired_replicas": 3,
            }
        ).status
        == "not_recovered"
    )
    assert (
        service.verify(
            {
                "error_rate": None,
                "p95_ms": 120,
                "healthy_replicas": 3,
                "desired_replicas": 3,
            }
        ).status
        == "inconclusive"
    )
