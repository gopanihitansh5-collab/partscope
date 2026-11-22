from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.deps import SessionDep
from src.catalog import service as catalog_service
from src.graph import service as graph_service
from src.models import Category, EquipmentModel, Manufacturer, Part
from src.schemas.catalog import (
    CategoryOut,
    EquipmentModelOut,
    ImportResult,
    ManufacturerOut,
    PartDetail,
    PartImportRow,
    PartSearchRequest,
    PartSearchResponse,
    PartSummary,
    PartUpdate,
)
from src.schemas.compatibility import CompatibilityRankRequest, CompatibilityRankResponse

router = APIRouter(tags=["catalog"])


@router.get("/parts", response_model=PartSearchResponse)
def list_parts(
    session: SessionDep,
    query: str | None = None,
    category: str | None = None,
    manufacturer: str | None = None,
    status: str | None = None,
    criticality: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PartSearchResponse:
    request = PartSearchRequest(
        query=query,
        category=category,
        manufacturer=manufacturer,
        status=status,
        criticality=criticality,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        limit=limit,
        offset=offset,
    )
    return catalog_service.search(session, request)


@router.post("/parts/search", response_model=PartSearchResponse)
def search_parts(request: PartSearchRequest, session: SessionDep) -> PartSearchResponse:
    return catalog_service.search(session, request)


@router.get("/parts/{part_id}", response_model=PartDetail)
def get_part(part_id: int, session: SessionDep) -> PartDetail:
    detail = catalog_service.get_part_detail(session, part_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Part not found")
    return detail


@router.get("/parts/{part_id}/compatibilities", response_model=CompatibilityRankResponse)
def part_compatibilities(
    part_id: int, session: SessionDep, limit: int = Query(default=10, ge=1, le=50)
) -> CompatibilityRankResponse:
    if session.get(Part, part_id) is None:
        raise HTTPException(status_code=404, detail="Part not found")
    return graph_service.rank(
        session, CompatibilityRankRequest(part_id=part_id, limit=limit)
    )


@router.patch("/parts/{part_id}", response_model=PartSummary)
def update_part(part_id: int, payload: PartUpdate, session: SessionDep) -> PartSummary:
    part = catalog_service.update_part(session, part_id, payload, actor="api-user")
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")
    return PartSummary.model_validate(part)


@router.post("/parts/import", response_model=ImportResult)
def import_parts(rows: list[PartImportRow], session: SessionDep) -> ImportResult:
    if len(rows) > 5000:
        raise HTTPException(status_code=413, detail="Import is limited to 5000 rows per request")
    return catalog_service.import_parts(session, rows, actor="api-user")


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(session: SessionDep) -> list[CategoryOut]:
    return [
        CategoryOut.model_validate(c)
        for c in session.scalars(select(Category).order_by(Category.name))
    ]


@router.get("/manufacturers", response_model=list[ManufacturerOut])
def list_manufacturers(session: SessionDep) -> list[ManufacturerOut]:
    return [
        ManufacturerOut.model_validate(m)
        for m in session.scalars(select(Manufacturer).order_by(Manufacturer.name))
    ]


@router.get("/equipment", response_model=list[EquipmentModelOut])
def list_equipment(session: SessionDep) -> list[EquipmentModelOut]:
    return [
        EquipmentModelOut.model_validate(e)
        for e in session.scalars(select(EquipmentModel).order_by(EquipmentModel.name))
    ]
