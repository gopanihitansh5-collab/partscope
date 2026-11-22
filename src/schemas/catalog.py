from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from src.schemas.common import ORMModel


class ManufacturerOut(ORMModel):
    id: int
    name: str
    country: str | None = None


class CategoryOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    criticality: str


class EquipmentModelOut(ORMModel):
    id: int
    name: str
    kind: str
    manufacturer_id: int | None = None


class SpecificationOut(ORMModel):
    id: int
    name: str
    value: str
    unit: str | None = None
    source_document_id: int | None = None


class PartSummary(ORMModel):
    id: int
    part_number: str
    name: str
    description: str | None = None
    manufacturer: ManufacturerOut | None = None
    category: CategoryOut | None = None
    price: float
    currency: str
    status: str
    criticality: str
    is_synthetic: bool


class CompatibilityOut(ORMModel):
    id: int
    relationship: str
    confidence: float
    source: str
    source_document_id: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    notes: str | None = None
    related_part: PartSummary | None = None


class PartDetail(PartSummary):
    specifications: list[SpecificationOut] = Field(default_factory=list)
    compatibilities: list[CompatibilityOut] = Field(default_factory=list)
    equipment_models: list[EquipmentModelOut] = Field(default_factory=list)
    inventory: list["InventoryOut"] = Field(default_factory=list)
    superseded_by: PartSummary | None = None


class InventoryOut(BaseModel):
    location: str
    region: str
    quantity: int
    snapshot_date: date


class PartSearchRequest(BaseModel):
    query: str | None = None
    category: str | None = None
    manufacturer: str | None = None
    status: str | None = None
    criticality: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    in_stock_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PartSearchResponse(BaseModel):
    total: int
    items: list[PartSummary]
    query: str | None = None
    synthetic_data: bool = True


class PartUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    status: str | None = None
    criticality: str | None = None
    category_id: int | None = None


class PartImportRow(BaseModel):
    part_number: str
    name: str
    description: str | None = None
    manufacturer: str | None = None
    category: str | None = None
    price: float = 0.0
    currency: str = "EUR"
    status: str = "active"


class ImportResult(BaseModel):
    accepted: int
    rejected: int
    errors: list[dict]
    created_ids: list[int]


class PartCreated(ORMModel):
    id: int
    part_number: str
    name: str
    created_at: datetime


PartDetail.model_rebuild()
