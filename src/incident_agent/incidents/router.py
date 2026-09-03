"""HTTP routes for Alertmanager ingestion and Incident queries."""

import hashlib
import hmac
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .schemas import AlertmanagerWebhook
from .service import AlertIngestService

router = APIRouter(prefix="/v1")


def get_service(request: Request) -> AlertIngestService:
    return AlertIngestService(request.app.state.repository)


@router.post("/alerts/alertmanager", status_code=202, response_model=None)
async def ingest_alertmanager(
    request: Request,
    service: Annotated[AlertIngestService, Depends(get_service)],
) -> JSONResponse:
    settings = request.app.state.settings
    body = await request.body()
    if len(body) > settings.max_alert_payload_bytes:
        from incident_agent.shared.errors import problem_response

        return problem_response(
            type="https://aiops.local/problems/payload-too-large",
            title="Payload too large",
            status=413,
            detail="request body exceeds configured limit",
            instance=str(request.url.path),
        )
    if settings.require_webhook_signature:
        timestamp = request.headers.get("X-AIOps-Timestamp")
        signature = request.headers.get("X-AIOps-Signature", "")
        valid_timestamp = False
        try:
            valid_timestamp = abs(time.time() - int(timestamp or "0")) <= 300
        except ValueError:
            pass
        expected = hmac.new(
            (settings.alertmanager_webhook_secret or "").encode(),
            f"{timestamp}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        if not valid_timestamp or not hmac.compare_digest(signature, f"v1={expected}"):
            from incident_agent.shared.errors import problem_response

            return problem_response(
                type="https://aiops.local/problems/invalid-webhook-signature",
                title="Invalid webhook signature",
                status=401,
                detail="webhook authentication failed",
                instance=str(request.url.path),
            )
    try:
        payload = AlertmanagerWebhook.model_validate_json(body)
    except ValidationError as exc:
        from incident_agent.shared.errors import problem_response

        return problem_response(
            type="https://aiops.local/problems/validation-error",
            title="Request validation failed",
            status=422,
            detail="request payload failed validation",
            instance=str(request.url.path),
            extensions={"errors": exc.errors()},
        )
    result = service.ingest(payload)
    return JSONResponse(
        status_code=202,
        content={
            "incident_ids": result.incident_ids,
            "created_incident_ids": result.created_incident_ids,
            "duplicate_alerts": result.duplicate_alerts,
        },
    )


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
