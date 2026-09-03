"""Recovery verification rules independent from action execution success."""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: Literal["recovered", "not_recovered", "inconclusive"]
    reason: str


class VerificationService:
    def verify(self, signals: dict[str, Any]) -> VerificationResult:
        required = ("error_rate", "p95_ms", "healthy_replicas", "desired_replicas")
        if any(signals.get(key) is None for key in required):
            return VerificationResult("inconclusive", "verification signal missing")
        if (
            float(signals["error_rate"]) <= 0.05
            and float(signals["p95_ms"]) <= 500
            and int(signals["healthy_replicas"]) >= int(signals["desired_replicas"])
        ):
            return VerificationResult("recovered", "all recovery signals within policy")
        return VerificationResult(
            "not_recovered", "one or more recovery signals failed"
        )
