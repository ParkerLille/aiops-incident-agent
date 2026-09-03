"""Versioned offline scenario registry used by demos and evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    service: str
    ground_truth: str
    legal_runbook: str


_SCENARIOS = {
    "order_db_slow_query": Scenario(
        "order_db_slow_query",
        "orders",
        "new image introduced an unindexed query",
        "rollback_deployment",
    ),
    "inventory_redis_pool": Scenario(
        "inventory_redis_pool",
        "inventory",
        "redis connection pool exhausted",
        "restart_deployment",
    ),
    "payment_config_error": Scenario(
        "payment_config_error",
        "payment",
        "payment endpoint configuration is invalid",
        "rollback_deployment",
    ),
}


def list_scenarios() -> list[Scenario]:
    return list(_SCENARIOS.values())


def get_scenario(name: str) -> Scenario:
    try:
        return _SCENARIOS[name]
    except KeyError as exc:
        raise ValueError(f"unknown scenario: {name}") from exc
