from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=6, ge=1, le=20)
    category: str | None = None
    part_id: int | None = None
    approved_only: bool = True


class RetrievedChunk(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    doc_type: str
    page: int
    section: str | None = None
    text: str
    score: float
    vector_score: float
    entity_score: float
    graph_score: float
    source: str


class RetrievalSearchResponse(BaseModel):
    query: str
    chunks: list[RetrievedChunk]
    total: int
    strategy: str
    latency_ms: float


class AnswerRequest(RetrievalSearchRequest):
    part_id: int | None = None


class Citation(BaseModel):
    document_id: int
    document_title: str
    page: int
    section: str | None = None
    chunk_id: int
    score: float


class AnswerResponse(BaseModel):
    query: str
    answer: str
    citations: list[Citation]
    confidence: float
    grounded: bool
    insufficient_evidence: bool
    warnings: list[str] = Field(default_factory=list)
    chunks: list[RetrievedChunk] = Field(default_factory=list)


class IndexRequest(BaseModel):
    rebuild: bool = True


class IndexResponse(BaseModel):
    documents: int
    chunks: int
    vocab_size: int
    artifact_path: str
    latency_ms: float
