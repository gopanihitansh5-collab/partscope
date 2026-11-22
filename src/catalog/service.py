"""Catalog search, detail assembly and audit-safe mutations."""

from __future__ import annotations

import difflib
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.common.utils import utcnow
from src.models import (
    AuditEvent,
    Category,
    Compatibility,
    EquipmentModel,
    EquipmentPart,
    InventoryLocation,
    InventorySnapshot,
    Manufacturer,
    Part,
    PartSpecification,
    Prediction,
)
from src.schemas.catalog import (
    CompatibilityOut,
    ImportResult,
    InventoryOut,
    PartDetail,
    PartImportRow,
    PartSearchRequest,
    PartSearchResponse,
    PartSummary,
    PartUpdate,
    SpecificationOut,
)


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 1}


def _search_text(part: Part) -> str:
    parts = [part.part_number, part.name, part.description or ""]
    if part.category:
        parts.append(part.category.name)
    if part.manufacturer:
        parts.append(part.manufacturer.name)
    for spec in part.specifications:
        parts.append(f"{spec.name} {spec.value} {spec.unit or ''}")
    return " ".join(parts)


def score_part(part: Part, query: str) -> float:
    q = query.lower().strip()
    if not q:
        return 0.0
    pn = part.part_number.lower()
    name = part.name.lower()
    haystack = _search_text(part).lower()

    score = 0.0
    if q == pn:
        score += 120
    elif q in pn:
        score += 90
    if q in name:
        score += 55
    if q in haystack:
        score += 25

    q_tokens = _tokens(q)
    hay_tokens = _tokens(haystack)
    overlap = len(q_tokens & hay_tokens)
    if q_tokens:
        score += 40 * (overlap / len(q_tokens))

    score += 35 * difflib.SequenceMatcher(None, q, pn).ratio()
    if part.criticality in {"critical", "high"}:
        score += 2
    return round(score, 4)


def latest_stock(session: Session, part_ids: list[int] | None = None) -> dict[int, int]:
    stmt = select(
        InventorySnapshot.part_id,
        InventorySnapshot.location_id,
        InventorySnapshot.quantity,
        InventorySnapshot.snapshot_date,
    )
    if part_ids:
        stmt = stmt.where(InventorySnapshot.part_id.in_(part_ids))
    latest: dict[int, tuple] = {}
    for part_id, location_id, qty, snapshot_date in session.execute(stmt):
        key = part_id
        if key not in latest or snapshot_date > latest[key][0]:
            latest[key] = (snapshot_date, {location_id: qty})
        elif snapshot_date == latest[key][0]:
            latest[key][1][location_id] = qty
    return {pid: sum(locs.values()) for pid, (_, locs) in latest.items()}


def search(session: Session, request: PartSearchRequest) -> PartSearchResponse:
    stmt = select(Part)
    if request.category:
        stmt = stmt.join(Category, Part.category_id == Category.id).where(
            (Category.slug == request.category) | (Category.name.ilike(f"%{request.category}%"))
        )
    if request.manufacturer:
        stmt = stmt.join(Manufacturer, Part.manufacturer_id == Manufacturer.id).where(
            Manufacturer.name.ilike(f"%{request.manufacturer}%")
        )
    if request.status:
        stmt = stmt.where(Part.status == request.status)
    if request.criticality:
        stmt = stmt.where(Part.criticality == request.criticality)
    if request.min_price is not None:
        stmt = stmt.where(Part.price >= request.min_price)
    if request.max_price is not None:
        stmt = stmt.where(Part.price <= request.max_price)

    candidates = list(session.scalars(stmt).unique())

    if request.in_stock_only:
        stock = latest_stock(session, [p.id for p in candidates])
        candidates = [p for p in candidates if stock.get(p.id, 0) > 0]

    if request.query:
        ranked = [(score_part(p, request.query), p) for p in candidates]
        ranked = [(s, p) for s, p in ranked if s > 12]
        ranked.sort(key=lambda item: (-item[0], item[1].part_number))
        candidates = [p for _, p in ranked]
    else:
        candidates.sort(key=lambda p: p.part_number)

    total = len(candidates)
    page = candidates[request.offset : request.offset + request.limit]
    return PartSearchResponse(
        total=total,
        items=[PartSummary.model_validate(p) for p in page],
        query=request.query,
    )


def inventory_for_part(session: Session, part_id: int) -> list[InventoryOut]:
    rows = session.execute(
        select(InventorySnapshot, InventoryLocation)
        .join(InventoryLocation, InventorySnapshot.location_id == InventoryLocation.id)
        .where(InventorySnapshot.part_id == part_id)
        .order_by(InventorySnapshot.snapshot_date.desc())
    ).all()
    latest_by_location: dict[int, tuple] = {}
    for snapshot, location in rows:
        if location.id not in latest_by_location:
            latest_by_location[location.id] = (snapshot, location)
    return [
        InventoryOut(
            location=location.name,
            region=location.region,
            quantity=snapshot.quantity,
            snapshot_date=snapshot.snapshot_date,
        )
        for snapshot, location in latest_by_location.values()
    ]


def get_part_detail(session: Session, part_id: int) -> PartDetail | None:
    part = session.get(Part, part_id)
    if not part:
        return None

    compat_rows = list(
        session.scalars(
            select(Compatibility)
            .where(Compatibility.part_id == part_id)
            .order_by(Compatibility.confidence.desc())
        )
    )
    equipment_ids = list(
        session.scalars(
            select(EquipmentPart.equipment_model_id).where(EquipmentPart.part_id == part_id)
        )
    )
    equipment = (
        list(session.scalars(select(EquipmentModel).where(EquipmentModel.id.in_(equipment_ids))))
        if equipment_ids
        else []
    )
    superseded_by = session.get(Part, part.superseded_by_id) if part.superseded_by_id else None

    detail = PartDetail(
        **PartSummary.model_validate(part).model_dump(),
        specifications=[SpecificationOut.model_validate(s) for s in part.specifications],
        compatibilities=[
            CompatibilityOut.model_validate(c) for c in compat_rows if c.related_part is not None
        ],
        equipment_models=[
            {"id": e.id, "name": e.name, "kind": e.kind, "manufacturer_id": e.manufacturer_id}
            for e in equipment
        ],
        inventory=inventory_for_part(session, part_id),
        superseded_by=PartSummary.model_validate(superseded_by) if superseded_by else None,
    )
    return detail


def get_by_number(session: Session, part_number: str) -> Part | None:
    return session.scalar(select(Part).where(func.lower(Part.part_number) == part_number.lower()))


def update_part(session: Session, part_id: int, payload: PartUpdate, actor: str = "system") -> Part | None:
    part = session.get(Part, part_id)
    if not part:
        return None
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(part, key, value)
    part.updated_at = utcnow()
    session.add(
        AuditEvent(
            actor=actor,
            action="part.update",
            entity_type="part",
            entity_id=str(part_id),
            payload={"changes": changes},
        )
    )
    session.commit()
    session.refresh(part)
    return part


def import_parts(session: Session, rows: list[PartImportRow], actor: str = "system") -> ImportResult:
    accepted = 0
    rejected = 0
    errors: list[dict] = []
    created_ids: list[int] = []

    categories = {c.name.lower(): c for c in session.scalars(select(Category))}
    manufacturers = {m.name.lower(): m for m in session.scalars(select(Manufacturer))}

    for index, row in enumerate(rows):
        if session.scalar(select(Part.id).where(Part.part_number == row.part_number)):
            rejected += 1
            errors.append({"row": index, "part_number": row.part_number, "error": "duplicate part_number"})
            continue
        category = categories.get((row.category or "").lower())
        manufacturer = manufacturers.get((row.manufacturer or "").lower())
        if row.category and not category:
            rejected += 1
            errors.append({"row": index, "part_number": row.part_number, "error": "unknown category"})
            continue
        if row.manufacturer and not manufacturer:
            rejected += 1
            errors.append({"row": index, "part_number": row.part_number, "error": "unknown manufacturer"})
            continue

        part = Part(
            part_number=row.part_number,
            name=row.name,
            description=row.description,
            manufacturer_id=manufacturer.id if manufacturer else None,
            category_id=category.id if category else None,
            price=row.price,
            currency=row.currency,
            status=row.status,
        )
        session.add(part)
        session.flush()
        created_ids.append(part.id)
        accepted += 1

    session.add(
        AuditEvent(
            actor=actor,
            action="part.import",
            entity_type="part",
            entity_id=None,
            payload={"accepted": accepted, "rejected": rejected},
        )
    )
    session.commit()
    return ImportResult(accepted=accepted, rejected=rejected, errors=errors, created_ids=created_ids)


def catalog_stats(session: Session) -> dict:
    return {
        "parts": session.query(Part).count(),
        "categories": session.query(Category).count(),
        "manufacturers": session.query(Manufacturer).count(),
        "specifications": session.query(PartSpecification).count(),
        "compatibilities": session.query(Compatibility).count(),
        "predictions": session.query(Prediction).count(),
    }
