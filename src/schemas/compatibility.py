from __future__ import annotations

from pydantic import BaseModel, Field


class GraphPathStep(BaseModel):
    part_id: int
    part_number: str
    name: str
    relationship: str
    confidence: float


class RankedCandidate(BaseModel):
    part_id: int
    part_number: str
    name: str
    category: str | None = None
    score: float
    relationship: str
    confidence: float
    source: str
    source_document_id: int | None = None
    evidence: list[GraphPathStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CompatibilityRankRequest(BaseModel):
    part_id: int | None = None
    part_number: str | None = None
    equipment_model: str | None = None
    limit: int = Field(default=5, ge=1, le=50)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CompatibilityRankResponse(BaseModel):
    source_part_id: int
    source_part_number: str
    candidates: list[RankedCandidate]
    algorithm: str
    graph_nodes: int
    graph_edges: int
    synthetic_data: bool = True


class VerifyRequest(BaseModel):
    part_id: int
    candidate_part_id: int


class VerifyResponse(BaseModel):
    verified: bool
    relationship: str | None = None
    confidence: float
    evidence: list[GraphPathStep] = Field(default_factory=list)
    reason: str
