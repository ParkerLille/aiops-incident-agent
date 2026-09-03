"""FastAPI application factory for the incident agent."""

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from incident_agent.incidents.repository import IncidentRepository
from incident_agent.incidents.router import router as incidents_router
from incident_agent.shared.config import Settings, get_settings
from incident_agent.shared.database import create_engine_and_session, database_probe
from incident_agent.shared.errors import problem_response
from incident_agent.shared.health import ProbeResult, check_dependencies


def create_app(
    settings: Settings | None = None,
    repository: IncidentRepository | None = None,
    probes: dict[str, Callable] | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    if repository is None:
        engine, session_factory = create_engine_and_session(app_settings.database_url)
        repository = IncidentRepository(session_factory)
    else:
        engine = None
    repository.create_tables()
    app = FastAPI(title="AIOps Incident Agent", version="0.1.0")
    app.state.settings = app_settings
    app.state.repository = repository
    app.state.engine = engine
    app.state.probes = probes or {
        "database": database_probe(engine),
        "redis": (lambda: ProbeResult.disabled()),
    }

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return problem_response(
            type="https://aiops.local/problems/validation-error",
            title="Request validation failed",
            status=422,
            detail="request payload failed validation",
            instance=str(request.url.path),
            extensions={"errors": exc.errors()},
        )

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        results = await check_dependencies(app.state.probes)
        unavailable = {
            name: result.detail or "unavailable"
            for name, result in results.items()
            if result.status == "unavailable"
        }
        if unavailable:
            return problem_response(
                type="https://aiops.local/problems/dependencies-unavailable",
                title="Dependencies unavailable",
                status=503,
                detail="one or more dependencies are unavailable",
                instance="/ready",
                extensions={"dependencies": unavailable},
            )
        return JSONResponse(
            {
                "status": "ready",
                "dependencies": {
                    name: result.status for name, result in results.items()
                },
            }
        )

    app.include_router(incidents_router)
    if app_settings.environment != "production":
        from incident_agent.lab.scenarios import get_scenario, list_scenarios

        @app.get("/v1/lab/scenarios")
        async def lab_scenarios() -> list[dict[str, str]]:
            return [
                {
                    "name": scenario.name,
                    "service": scenario.service,
                    "ground_truth": scenario.ground_truth,
                    "legal_runbook": scenario.legal_runbook,
                }
                for scenario in list_scenarios()
            ]

        @app.post("/v1/lab/scenarios/{name}/inject")
        async def inject_scenario(name: str) -> dict[str, str]:
            scenario = get_scenario(name)
            return {
                "scenario": scenario.name,
                "status": "injected",
                "service": scenario.service,
            }

    return app
