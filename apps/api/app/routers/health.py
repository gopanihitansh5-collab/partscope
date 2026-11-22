from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.deps import SessionDep
from src.common.config import settings

router = APIRouter(tags=["system"])


@router.get("/health/live")
def live() -> dict:
    return {"status": "ok", "version": settings.app_version, "env": settings.app_env}


@router.get("/health/ready")
def ready(session: SessionDep):
    checks: dict[str, dict] = {}
    ok = True

    try:
        session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "url": settings.database_url.split("@")[-1]}
    except Exception as exc:  # noqa: BLE001
        ok = False
        checks["database"] = {"status": "error", "detail": str(exc)}

    artifacts = {
        "vision": settings.artifact_path / "vision" / "baseline" / "embeddings.npz",
        "forecast": settings.artifact_path / "forecasting" / "model.joblib",
        "retrieval": settings.artifact_path / "retrieval" / "index.joblib",
    }
    for name, path in artifacts.items():
        checks[name] = {"status": "ok" if path.exists() else "missing", "path": str(path)}
        if not path.exists():
            ok = False

    payload = {"status": "ok" if ok else "degraded", "checks": checks}
    return JSONResponse(status_code=200 if ok else 503, content=payload)
