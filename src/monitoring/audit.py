from __future__ import annotations

from sqlalchemy.orm import Session

from src.models import AuditEvent


def record_audit(
    session: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    payload: dict | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        payload=payload or {},
        request_id=request_id,
    )
    session.add(event)
    session.commit()
    return event
