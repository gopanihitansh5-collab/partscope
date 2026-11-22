from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.common import ORMModel


class AgentRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    part_id: int | None = None
    image_id: str | None = None
    include_forecast: bool = True
    include_retrieval: bool = True
    include_compatibility: bool = True


class TraceEvent(BaseModel):
    node: str
    status: str
    detail: str | None = None
    latency_ms: float | None = None
    at: datetime


class ToolRunOut(ORMModel):
    id: int
    tool_name: str
    status: str
    latency_ms: float | None
    input: dict
    output: dict
    error: str | None
    created_at: datetime


class AgentRunOut(BaseModel):
    run_id: str
    query: str
    status: str
    intent: str | None
    response: dict | None
    trace: list[dict]
    error: str | None
    latency_ms: float | None
    created_at: datetime
    finished_at: datetime | None


class AgentRunDetail(AgentRunOut):
    tool_runs: list[ToolRunOut] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class UploadResponse(BaseModel):
    image_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int
    message: str = "Upload accepted. Use image_id with /api/v1/vision/identify or /api/v1/agent/runs."
