import pytest

from incident_agent.shared.health import ProbeResult, check_dependencies


@pytest.mark.asyncio
async def test_all_dependencies_ready():
    result = await check_dependencies(
        {"database": lambda: ProbeResult.ok(), "redis": lambda: ProbeResult.disabled()}
    )
    assert result["database"].status == "ok"
    assert result["redis"].status == "disabled"


@pytest.mark.asyncio
async def test_failed_dependency_is_reported_without_raising():
    result = await check_dependencies(
        {"database": lambda: ProbeResult.failed("connection refused")}
    )
    assert result["database"].status == "unavailable"
    assert result["database"].detail == "connection refused"
