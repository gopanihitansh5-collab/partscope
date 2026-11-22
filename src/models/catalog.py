from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.db import Base
from src.common.utils import utcnow


class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    country: Mapped[str | None] = mapped_column(String(80))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)

    parts: Mapped[list[Part]] = relationship(back_populates="manufacturer")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    criticality: Mapped[str] = mapped_column(String(20), default="standard")

    parts: Mapped[list[Part]] = relationship(back_populates="category")


class EquipmentModel(Base):
    __tablename__ = "equipment_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    manufacturer_id: Mapped[int | None] = mapped_column(ForeignKey("manufacturers.id"))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)

    manufacturer: Mapped[Manufacturer | None] = relationship()


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    manufacturer_id: Mapped[int | None] = mapped_column(ForeignKey("manufacturers.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    status: Mapped[str] = mapped_column(String(24), default="active")
    criticality: Mapped[str] = mapped_column(String(20), default="standard")
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    manufacturer: Mapped[Manufacturer | None] = relationship(back_populates="parts", lazy="joined")
    category: Mapped[Category | None] = relationship(back_populates="parts", lazy="joined")
    specifications: Mapped[list[PartSpecification]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )


class PartSpecification(Base):
    __tablename__ = "part_specifications"
    __table_args__ = (UniqueConstraint("part_id", "name", name="uq_spec_part_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(32))
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))

    part: Mapped[Part] = relationship(back_populates="specifications")


class Compatibility(Base):
    __tablename__ = "compatibilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    related_part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(
        "relationship", String(24)
    )  # compatible|replaces|supersedes
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    source: Mapped[str] = mapped_column(String(160), default="synthetic-manual")
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)

    part: Mapped[Part] = relationship(foreign_keys=[part_id])
    related_part: Mapped[Part] = relationship(foreign_keys=[related_part_id], lazy="joined")


class EquipmentPart(Base):
    __tablename__ = "equipment_parts"
    __table_args__ = (UniqueConstraint("part_id", "equipment_model_id", name="uq_part_equipment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"), index=True)
    equipment_model_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_models.id", ondelete="CASCADE"), index=True
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)
    reliability: Mapped[float] = mapped_column(Float, default=0.9)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class PartSupplier(Base):
    __tablename__ = "part_suppliers"
    __table_args__ = (UniqueConstraint("part_id", "supplier_id", name="uq_part_supplier"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)
