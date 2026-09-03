"""Small factual postmortem renderer."""

from collections.abc import Sequence
from typing import Any


def render_postmortem(
    incident: dict[str, Any],
    facts: Sequence[str],
    inferences: Sequence[str],
    actions: Sequence[str],
) -> str:
    def section(title: str, items: Sequence[str]) -> str:
        lines = "\n".join(f"- {item}" for item in items) or "- 无"
        return f"## {title}\n{lines}"

    header = (
        f"# Incident {incident.get('id', 'unknown')}\n\n"
        f"服务：{incident.get('service', 'unknown')}\n"
        f"状态：{incident.get('status', 'unknown')}"
    )
    return "\n\n".join(
        [
            header,
            section("事实", facts),
            section("推断", inferences),
            section("后续行动", actions),
        ]
    )
