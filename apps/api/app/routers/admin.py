from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.deps import SessionDep
from src.catalog import service as catalog_service
from src.common.config import settings
from src.graph import service as graph_service
from src.models import AuditEvent, ModelVersion
from src.schemas.common import AuditEventOut
from src.schemas.forecast import ModelVersionOut

router = APIRouter(tags=["admin"], prefix="/admin")


@router.get("/models", response_model=list[ModelVersionOut])
def models(session: SessionDep, task: str | None = None) -> list[ModelVersionOut]:
    stmt = select(ModelVersion).order_by(ModelVersion.id.desc())
    if task:
        stmt = stmt.where(ModelVersion.task == task)
    return [ModelVersionOut.model_validate(m) for m in session.scalars(stmt)]


@router.get("/audit", response_model=list[AuditEventOut])
def audit(
    session: SessionDep,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AuditEventOut]:
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    return [AuditEventOut.model_validate(e) for e in session.scalars(stmt)]


@router.get("/imports")
def imports(session: SessionDep, limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == "part.import")
        .order_by(AuditEvent.id.desc())
        .limit(limit)
    )
    return [
        {
            "id": event.id,
            "actor": event.actor,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]


@router.get("/stats")
def stats(session: SessionDep) -> dict:
    artifacts = {
        "vision": settings.artifact_path / "vision" / "baseline" / "metadata.json",
        "forecast": settings.artifact_path / "forecasting" / "metadata.json",
        "retrieval": settings.artifact_path / "retrieval" / "metadata.json",
    }
    return {
        "catalog": catalog_service.catalog_stats(session),
        "graph": graph_service.graph_stats(session),
        "artifacts": {
            name: {"present": path.exists(), "path": str(path)}
            for name, path in artifacts.items()
        },
        "synthetic_data": True,
    }
