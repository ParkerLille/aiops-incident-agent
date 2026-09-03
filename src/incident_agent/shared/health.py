"""Dependency readiness probes."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from inspect import isawaitable
from typing import Literal

ProbeStatus = Literal["ok", "disabled", "unavailable"]
ProbeCallable = Callable[[], "ProbeResult | Awaitable[ProbeResult]"]


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: ProbeStatus
    detail: str | None = None

    @classmethod
    def ok(cls) -> "ProbeResult":
        return cls("ok")

    @classmethod
    def disabled(cls) -> "ProbeResult":
        return cls("disabled")

    @classmethod
    def failed(cls, detail: str) -> "ProbeResult":
        return cls("unavailable", detail)


async def check_dependencies(
    probes: dict[str, ProbeCallable],
) -> dict[str, ProbeResult]:
    """Run all probes and convert failures into stable unavailable results."""

    results: dict[str, ProbeResult] = {}
    for name, probe in probes.items():
        try:
            result = probe()
            if isawaitable(result):
                result = await result
            results[name] = result
        except Exception as exc:  # probes must never bring down readiness endpoint
            results[name] = ProbeResult.failed(str(exc))
    return results
