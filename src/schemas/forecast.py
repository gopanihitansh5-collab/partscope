from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    part_id: int | None = None
    part_number: str | None = None
    horizon_days: int = Field(default=30, ge=7, le=180)


class ForecastDriver(BaseModel):
    feature: str
    impact: float
    direction: str


class ForecastResponse(BaseModel):
    part_id: int
    part_number: str
    part_name: str
    horizon_days: int
    expected_demand: float
    lower_bound: float
    upper_bound: float
    current_stock: float
    predicted_stock: float
    shortage_probability: float
    reorder_quantity: float
    risk_level: str
    model_name: str
    model_version: str
    metrics: dict
    drivers: list[ForecastDriver] = Field(default_factory=list)
    data_freshness: date | None = None
    warnings: list[str] = Field(default_factory=list)
    synthetic_data: bool = True


class ForecastEvaluateRequest(BaseModel):
    test_days: int = Field(default=60, ge=14, le=180)


class ForecastEvaluateResponse(BaseModel):
    model_name: str
    model_version: str
    baseline_metrics: dict
    model_metrics: dict
    improvement: dict
    calibration: dict
    report_path: str | None = None


class ModelVersionOut(BaseModel):
    id: int
    name: str
    version: str
    task: str
    runtime: str
    precision: str
    artifact_uri: str | None
    metrics: dict
    approved: bool
    created_at: datetime
