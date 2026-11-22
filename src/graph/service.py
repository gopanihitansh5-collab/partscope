"""Compatibility graph traversal and ranking.

The graph is stored as an indexed edge table in PostgreSQL/SQLite. The public
interface is deliberately graph-shaped so a Neo4j adapter can replace the
storage layer without touching callers.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import (
    Compatibility,
    EquipmentPart,
    Part,
    PartSpecification,
    PartSupplier,
    Supplier,
)
from src.schemas.compatibility import (
    CompatibilityRankRequest,
    CompatibilityRankResponse,
    GraphPathStep,
    RankedCandidate,
    VerifyResponse,
)

RELATIONSHIP_WEIGHT = {
    "supersedes": 1.0,
    "replaces": 0.95,
    "compatible": 0.85,
    "shared_equipment": 0.55,
}

DECAY_PER_HOP = 0.72
MAX_DEPTH = 2


@dataclass
class Edge:
    source_id: int
    target_id: int
    relationship: str
    confidence: float
    source: str
    source_document_id: int | None
    hops: int = 1


@dataclass
class Candidate:
    part: Part
    score: float
    relationship: str
    confidence: float
    source: str
    source_document_id: int | None
    path: list[Edge] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _valid_on(edge: Compatibility, today: date) -> bool:
    if edge.valid_from and edge.valid_from > today:
        return False
    if edge.valid_to and edge.valid_to < today:
        return False
    return True


def load_adjacency(session: Session) -> dict[int, list[Edge]]:
    today = date.today()
    adjacency: dict[int, list[Edge]] = {}
    for edge in session.scalars(select(Compatibility)):
        if not _valid_on(edge, today):
            continue
        adjacency.setdefault(edge.part_id, []).append(
            Edge(
                source_id=edge.part_id,
                target_id=edge.related_part_id,
                relationship=edge.relationship_type,
                confidence=edge.confidence,
                source=edge.source,
                source_document_id=edge.source_document_id,
            )
        )
    return adjacency


def _spec_map(session: Session, part_ids: list[int]) -> dict[int, set[tuple[str, str]]]:
    rows = session.execute(
        select(PartSpecification.part_id, PartSpecification.name, PartSpecification.value).where(
            PartSpecification.part_id.in_(part_ids)
        )
    ).all()
    specs: dict[int, set[tuple[str, str]]] = {}
    for part_id, name, value in rows:
        specs.setdefault(part_id, set()).add((name.lower(), value.lower()))
    return specs


def _equipment_map(session: Session, part_ids: list[int]) -> dict[int, set[int]]:
    rows = session.execute(
        select(EquipmentPart.part_id, EquipmentPart.equipment_model_id).where(
            EquipmentPart.part_id.in_(part_ids)
        )
    ).all()
    mapping: dict[int, set[int]] = {}
    for part_id, equipment_id in rows:
        mapping.setdefault(part_id, set()).add(equipment_id)
    return mapping


def _shared_equipment_edges(session: Session, source: Part, part_ids: list[int]) -> list[Edge]:
    source_equipment = set(
        session.scalars(
            select(EquipmentPart.equipment_model_id).where(EquipmentPart.part_id == source.id)
        )
    )
    if not source_equipment:
        return []
    peer_rows = session.execute(
        select(EquipmentPart.part_id, EquipmentPart.equipment_model_id).where(
            EquipmentPart.equipment_model_id.in_(source_equipment),
            EquipmentPart.part_id != source.id,
        )
    ).all()
    edges: list[Edge] = []
    seen: set[int] = set()
    for part_id, _equipment_id in peer_rows:
        if part_id in seen or part_id not in part_ids:
            continue
        seen.add(part_id)
        edges.append(
            Edge(
                source_id=source.id,
                target_id=part_id,
                relationship="shared_equipment",
                confidence=0.55,
                source="catalog-equipment-fitment",
                source_document_id=None,
            )
        )
        if len(edges) >= 40:
            break
    return edges


def rank(
    session: Session, request: CompatibilityRankRequest, part_ids: list[int] | None = None
) -> CompatibilityRankResponse:
    source: Part | None = None
    if request.part_id:
        source = session.get(Part, request.part_id)
    elif request.part_number:
        source = session.scalar(select(Part).where(Part.part_number == request.part_number))
    if source is None:
        raise ValueError("Source part not found. Provide part_id or part_number.")

    all_parts = {p.id: p for p in session.scalars(select(Part))}
    ids = part_ids or list(all_parts.keys())
    adjacency = load_adjacency(session)
    equipment_edges = _shared_equipment_edges(session, source, set(ids))
    adjacency.setdefault(source.id, []).extend(equipment_edges)

    specs = _spec_map(session, list(ids))
    equipment = _equipment_map(session, list(ids))

    best: dict[int, Candidate] = {}
    queue: deque[tuple[int, float, list[Edge], set[int]]] = deque(
        [(source.id, 1.0, [], {source.id})]
    )

    while queue:
        node_id, path_score, path, visited = queue.popleft()
        if len(path) >= MAX_DEPTH:
            continue
        for edge in adjacency.get(node_id, []):
            if edge.target_id in visited or edge.target_id not in all_parts:
                continue
            if edge.target_id not in ids:
                continue
            if edge.confidence < request.min_confidence:
                continue

            weight = RELATIONSHIP_WEIGHT.get(edge.relationship, 0.5)
            hop_score = path_score * weight * edge.confidence * (DECAY_PER_HOP ** len(path))
            new_path = [*path, edge]

            candidate_part = all_parts[edge.target_id]
            existing = best.get(candidate_part.id)
            if existing is None or hop_score > existing.score:
                best[candidate_part.id] = Candidate(
                    part=candidate_part,
                    score=hop_score,
                    relationship=edge.relationship,
                    confidence=edge.confidence,
                    source=edge.source,
                    source_document_id=edge.source_document_id,
                    path=new_path,
                )

            if len(new_path) < MAX_DEPTH:
                queue.append((edge.target_id, hop_score, new_path, visited | {edge.target_id}))

    ranked: list[RankedCandidate] = []
    for candidate in best.values():
        shared = specs.get(source.id, set()) & specs.get(candidate.part.id, set())
        shared_equipment = equipment.get(source.id, set()) & equipment.get(candidate.part.id, set())
        bonus = min(0.15, 0.03 * len(shared)) + (0.06 if shared_equipment else 0.0)
        score = min(1.0, candidate.score + bonus)

        warnings: list[str] = []
        if candidate.source_document_id is None:
            warnings.append("No approved source document is linked to this relationship.")
        if candidate.confidence < 0.7:
            warnings.append("Relationship confidence is below the review threshold.")
        if candidate.part.status in {"discontinued", "superseded"}:
            warnings.append(f"Part status is '{candidate.part.status}'; check supersession chain.")

        evidence = [
            GraphPathStep(
                part_id=all_parts[edge.target_id].id,
                part_number=all_parts[edge.target_id].part_number,
                name=all_parts[edge.target_id].name,
                relationship=edge.relationship,
                confidence=round(edge.confidence, 3),
            )
            for edge in candidate.path
        ]

        ranked.append(
            RankedCandidate(
                part_id=candidate.part.id,
                part_number=candidate.part.part_number,
                name=candidate.part.name,
                category=candidate.part.category.name if candidate.part.category else None,
                score=round(score, 4),
                relationship=candidate.relationship,
                confidence=round(candidate.confidence, 3),
                source=candidate.source,
                source_document_id=candidate.source_document_id,
                evidence=evidence,
                warnings=warnings,
            )
        )

    ranked.sort(key=lambda c: (-c.score, c.part_number))
    return CompatibilityRankResponse(
        source_part_id=source.id,
        source_part_number=source.part_number,
        candidates=ranked[: request.limit],
        algorithm=(
            "weighted multi-hop traversal (depth<=2) with relationship, confidence, "
            "shared-specification and shared-equipment bonuses"
        ),
        graph_nodes=len(all_parts),
        graph_edges=sum(len(v) for v in adjacency.values()),
    )


def verify(session: Session, part_id: int, candidate_part_id: int) -> VerifyResponse:
    today = date.today()
    edge = session.scalar(
        select(Compatibility).where(
            Compatibility.part_id == part_id,
            Compatibility.related_part_id == candidate_part_id,
        )
    )
    if edge and _valid_on(edge, today):
        session.get(Part, part_id)
        target = session.get(Part, candidate_part_id)
        return VerifyResponse(
            verified=edge.confidence >= 0.6,
            relationship=edge.relationship_type,
            confidence=edge.confidence,
            evidence=[
                GraphPathStep(
                    part_id=target.id if target else candidate_part_id,
                    part_number=target.part_number if target else str(candidate_part_id),
                    name=target.name if target else "unknown",
                    relationship=edge.relationship_type,
                    confidence=edge.confidence,
                )
            ],
            reason=(
                f"Approved {edge.relationship_type} relationship from source "
                f"'{edge.source}'."
                if edge.confidence >= 0.6
                else "Relationship exists but confidence is below the verification threshold."
            ),
        )

    reverse = session.scalar(
        select(Compatibility).where(
            Compatibility.part_id == candidate_part_id,
            Compatibility.related_part_id == part_id,
        )
    )
    if reverse and _valid_on(reverse, today):
        return VerifyResponse(
            verified=False,
            relationship=reverse.relationship_type,
            confidence=reverse.confidence,
            reason=(
                "A reverse relationship exists. Compatibility is directional: verify the "
                "direction of supersession before ordering."
            ),
        )
    return VerifyResponse(
        verified=False,
        relationship=None,
        confidence=0.0,
        reason="No approved relationship exists between these parts.",
    )


def graph_stats(session: Session) -> dict:
    parts = session.query(Part).count()
    edges = session.query(Compatibility).count()
    suppliers = session.query(Supplier).count()
    links = session.query(PartSupplier).count()
    return {
        "nodes": {"parts": parts, "suppliers": suppliers},
        "edges": {"compatibilities": edges, "part_supplier": links},
    }
