"""Application service for alert ingestion."""

from dataclasses import dataclass

from .repository import IncidentRepository
from .schemas import AlertmanagerWebhook


@dataclass(frozen=True, slots=True)
class IngestResponse:
    incident_ids: list[str]
    created_incident_ids: list[str]
    duplicate_alerts: int


class AlertIngestService:
    def __init__(self, repository: IncidentRepository):
        self.repository = repository

    def ingest(self, payload: AlertmanagerWebhook) -> IngestResponse:
        incident_ids: list[str] = []
        created_ids: list[str] = []
        duplicate_alerts = 0
        for alert in payload.alerts:
            result = self.repository.ingest_alert(alert)
            if result.incident_id not in incident_ids:
                incident_ids.append(result.incident_id)
            if result.created:
                if result.incident_id not in created_ids:
                    created_ids.append(result.incident_id)
            else:
                duplicate_alerts += 1
        return IngestResponse(incident_ids, created_ids, duplicate_alerts)
