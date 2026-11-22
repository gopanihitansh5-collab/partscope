from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.deps import SessionDep
from src.catalog import service as catalog_service
from src.forecasting import service as forecast_service
from src.models import DemandHistory, Part
from src.monitoring.metrics import FORECAST_LATENCY
from src.schemas.forecast import (
    ForecastEvaluateRequest,
    ForecastEvaluateResponse,
    ForecastRequest,
    ForecastResponse,
)

router = APIRouter(tags=["forecasting"])


def _resolve(session, part_id: int | None, part_number: str | None) -> int:
    if part_id:
        return part_id
    if part_number:
        part = catalog_service.get_by_number(session, part_number)
        if part:
            return part.id
    raise HTTPException(status_code=404, detail="Part not found. Provide part_id or part_number.")


@router.post("/forecast/demand", response_model=ForecastResponse)
def demand(request: ForecastRequest, session: SessionDep) -> ForecastResponse:
    part_id = _resolve(session, request.part_id, request.part_number)
    result = forecast_service.forecast_part(session, part_id, horizon_days=request.horizon_days)
    FORECAST_LATENCY.observe(0.0)
    return result


@router.get("/forecast/parts/{part_id}", response_model=ForecastResponse)
def part_forecast(
    part_id: int, session: SessionDep, horizon_days: int = Query(default=30, ge=7, le=180)
) -> ForecastResponse:
    return forecast_service.forecast_part(session, part_id, horizon_days=horizon_days)


@router.post("/forecast/evaluate", response_model=ForecastEvaluateResponse)
def evaluate(request: ForecastEvaluateRequest, session: SessionDep) -> ForecastEvaluateResponse:
    return ForecastEvaluateResponse(**forecast_service.evaluate(session))


@router.get("/forecast/overview")
def overview(session: SessionDep, limit: int = Query(default=10, ge=1, le=50)) -> dict:
    latest = session.scalar(select(func.max(DemandHistory.date)))
    if latest is None:
        raise HTTPException(status_code=404, detail="No demand history available")
    start = latest.fromordinal(latest.toordinal() - 29)
    rows = session.execute(
        select(DemandHistory.part_id, func.sum(DemandHistory.quantity))
        .where(DemandHistory.date >= start)
        .group_by(DemandHistory.part_id)
    ).all()
    expected = {part_id: float(total) for part_id, total in rows}
    part_ids = list(expected)
    stock = catalog_service.latest_stock(session, part_ids)
    parts = {
        p.id: p for p in session.scalars(select(Part).where(Part.id.in_(part_ids)))
    }

    items = []
    for part_id, expected_30d in expected.items():
        part = parts.get(part_id)
        if part is None:
            continue
        current_stock = float(stock.get(part_id, 0))
        risk = max(0.0, min(1.0, 1.0 - current_stock / (expected_30d + 1.0)))
        items.append(
            {
                "part_id": part_id,
                "part_number": part.part_number,
                "name": part.name,
                "category": part.category.name if part.category else None,
                "criticality": part.criticality,
                "expected_30d_demand": round(expected_30d, 2),
                "current_stock": current_stock,
                "shortage_risk": round(risk, 4),
                "risk_level": "high" if risk >= 0.6 else "medium" if risk >= 0.3 else "low",
            }
        )
    items.sort(key=lambda item: -item["shortage_risk"])
    return {
        "method": "inventory-cover preview (last-30-day demand vs latest stock); "
        "per-part POST /forecast/demand returns the trained model output",
        "as_of": latest.isoformat(),
        "items": items[:limit],
        "synthetic_data": True,
    }
