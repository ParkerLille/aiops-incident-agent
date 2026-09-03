"""SQLAlchemy repository for idempotent incident ingestion."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .fingerprint import compute_fingerprint
from .models import Alert, Base, Incident, TimelineEvent
from .schemas import AlertmanagerAlert, IncidentView


@dataclass(frozen=True, slots=True)
class IngestedAlert:
    incident_id: str
    created: bool


class IncidentRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def create_tables(self) -> None:
        bind = self._session_factory.kw["bind"]
        assert bind is not None
        Base.metadata.create_all(bind=bind)

    def ingest_alert(self, alert: AlertmanagerAlert) -> IngestedAlert:
        now = datetime.now(UTC)
        labels = dict(alert.labels)
        environment = labels["environment"]
        service = labels["service"]
        fingerprint = compute_fingerprint(labels)
        with self._session_factory() as session:
            existing = session.scalar(
                select(Alert).where(Alert.fingerprint == fingerprint)
            )
            if existing:
                return IngestedAlert(existing.incident_id, False)
            incident = session.scalar(
                select(Incident).where(
                    Incident.environment == environment,
                    Incident.service == service,
                    Incident.status == "open",
                )
            )
            if incident is None:
                incident = Incident(
                    environment=environment,
                    service=service,
                    severity=labels.get("severity", "warning"),
                    first_seen=alert.starts_at,
                    last_seen=alert.starts_at,
                    version=1,
                )
                session.add(incident)
                session.flush()
                session.add(
                    TimelineEvent(
                        incident_id=incident.id,
                        type="incident_created",
                        occurred_at=alert.starts_at,
                        payload={"service": service, "environment": environment},
                    )
                )
            incident.last_seen = max(incident.last_seen, alert.starts_at)
            incident.version += 1
            model = Alert(
                fingerprint=fingerprint,
                incident_id=incident.id,
                labels=labels,
                annotations=dict(alert.annotations),
                starts_at=alert.starts_at,
                ends_at=alert.ends_at,
                generator_url=alert.generator_url,
                created_at=now,
            )
            session.add(model)
            session.add(
                TimelineEvent(
                    incident_id=incident.id,
                    type="alert_received",
                    occurred_at=alert.starts_at,
                    payload={"fingerprint": fingerprint},
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(Alert).where(Alert.fingerprint == fingerprint)
                )
                if existing:
                    return IngestedAlert(existing.incident_id, False)
                raise
            return IngestedAlert(incident.id, True)

    def get_incident(self, incident_id: str) -> IncidentView | None:
        with self._session_factory() as session:
            incident = session.get(Incident, incident_id)
            if incident is None:
                return None
            return IncidentView(
                id=incident.id,
                environment=incident.environment,
                service=incident.service,
                severity=incident.severity,
                status=incident.status,
                first_seen=incident.first_seen,
                last_seen=incident.last_seen,
                version=incident.version,
                alerts=[
                    {
                        "id": alert.id,
                        "fingerprint": alert.fingerprint,
                        "labels": alert.labels,
                        "starts_at": alert.starts_at.isoformat(),
                    }
                    for alert in incident.alerts
                ],
                timeline=[
                    {
                        "id": event.id,
                        "type": event.type,
                        "occurred_at": event.occurred_at.isoformat(),
                        "payload": event.payload,
                    }
                    for event in incident.timeline
                ],
            )
