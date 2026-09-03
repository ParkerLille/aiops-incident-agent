"""HTTP routes for Alertmanager ingestion and Incident queries."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from .schemas import AlertmanagerWebhook
from .service import AlertIngestService, IngestResponse

router = APIRouter(prefix="/v1")


def get_service(request: Request) -> AlertIngestService:
    return AlertIngestService(request.app.state.repository)


@router.post("/alerts/alertmanager", status_code=202)
async def ingest_alertmanager(
    payload: AlertmanagerWebhook,
    service: Annotated[AlertIngestService, Depends(get_service)],
) -> IngestResponse:
    return service.ingest(payload)


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: UUID, request: Request) -> JSONResponse:
    incident = request.app.state.repository.get_incident(str(incident_id))
    if incident is None:
        from incident_agent.shared.errors import problem_response

        return problem_response(
            type="https://aiops.local/problems/incident-not-found",
            title="Incident not found",
            status=404,
            detail="incident does not exist",
            instance=f"/v1/incidents/{incident_id}",
        )
    return JSONResponse(incident.model_dump(mode="json"))
