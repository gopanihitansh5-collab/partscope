from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.common.db import Base
from src.common.utils import utcnow


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(String(48))  # classification|retrieval|forecast
    runtime: Mapped[str] = mapped_column(String(48), default="python")
    precision: Mapped[str] = mapped_column(String(16), default="fp32")
    artifact_uri: Mapped[str | None] = mapped_column(String(400))
    dataset_uri: Mapped[str | None] = mapped_column(String(400))
    dataset_hash: Mapped[str | None] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    horizon_days: Mapped[int] = mapped_column(Integer, default=30)
    expected_demand: Mapped[float] = mapped_column(Float, default=0.0)
    lower_bound: Mapped[float] = mapped_column(Float, default=0.0)
    upper_bound: Mapped[float] = mapped_column(Float, default=0.0)
    shortage_probability: Mapped[float] = mapped_column(Float, default=0.0)
    current_stock: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_stock: Mapped[float] = mapped_column(Float, default=0.0)
    reorder_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
