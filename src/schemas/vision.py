from __future__ import annotations

from pydantic import BaseModel, Field


class VisionCandidate(BaseModel):
    label: str
    part_id: int | None = None
    part_number: str | None = None
    category: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    rank: int


class VisionIdentifyResponse(BaseModel):
    model_name: str
    model_version: str
    runtime: str
    precision: str
    image_hash: str
    latency_ms: float
    top_candidates: list[VisionCandidate]
    confidence: float
    low_confidence: bool
    review_required: bool
    warnings: list[str] = Field(default_factory=list)
    synthetic_data: bool = True


class SimilarImageMatch(BaseModel):
    part_id: int | None = None
    part_number: str | None = None
    label: str
    similarity: float


class SimilarImageResponse(BaseModel):
    model_name: str
    model_version: str
    matches: list[SimilarImageMatch]
    latency_ms: float


class VisionEvaluateResponse(BaseModel):
    dataset: str
    samples: int
    top1_accuracy: float
    top5_accuracy: float
    macro_f1: float
    per_class_recall: dict[str, float]
    latency_ms_p50: float
    latency_ms_p95: float
    model_name: str
    model_version: str
    report_path: str | None = None
