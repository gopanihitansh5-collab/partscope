"""Deterministic synthetic dataset generator.

The generator is seeded, so the same database and image set are produced on
every machine. All records are labelled ``is_synthetic``/``synthetic``.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.config import settings
from src.common.db import Base, engine
from src.models import (
    Category,
    Compatibility,
    DemandHistory,
    Document,
    DocumentChunk,
    EquipmentModel,
    EquipmentPart,
    InventoryLocation,
    InventorySnapshot,
    Manufacturer,
    Part,
    PartSpecification,
    PartSupplier,
    Supplier,
)
from src.seed.definitions import (
    CATEGORY_DEFS,
    CATEGORY_EQUIPMENT_KINDS,
    DOC_TYPES,
    EQUIPMENT_DEFS,
    LOCATION_DEFS,
    MANUFACTURER_NAMES,
    SUPPLIER_NAMES,
    SeedStats,
)
from src.vision.synthetic import save_part_image

PARTS_PER_CATEGORY = 40
FAMILIES_PER_CATEGORY = 8
DEMAND_DAYS = 548  # ~18 months
INVENTORY_MONTHS = 12
SEED = 42

PRICE_RANGES = {
    "bearings": (12, 85),
    "filters": (8, 60),
    "drive-belts": (10, 55),
    "hydraulic-pumps": (280, 1450),
    "hydraulic-hoses": (35, 240),
    "electrical-relays": (14, 90),
    "brake-pads": (45, 260),
    "wheels-tires": (120, 680),
    "seals-gaskets": (6, 95),
    "fasteners": (0.8, 9),
    "transmission-gears": (140, 900),
    "cooling-fans": (90, 480),
    "lighting": (25, 180),
    "sensors": (110, 620),
    "cabin-seats": (450, 1900),
}

CATEGORY_PRICE_BASE = {k: (v[0] + v[1]) / 2 for k, v in PRICE_RANGES.items()}


def _mfr_code(name: str) -> str:
    letters = "".join(ch for ch in name.upper() if ch.isalpha())
    return letters[:2]


def _reset_schema() -> None:
    from src.models import Base as ModelsBase

    ModelsBase.metadata.drop_all(bind=engine)
    ModelsBase.metadata.create_all(bind=engine)


def seed_database(reset: bool = True) -> SeedStats:
    stats = SeedStats()
    if reset:
        _reset_schema()

    rng = np.random.default_rng(SEED)
    py_rng = random.Random(SEED)

    with Session(engine) as session:
        manufacturers = [Manufacturer(name=name, country=py_rng.choice(["BE", "DE", "US", "IN", "SE", "IT", "NL"])) for name in MANUFACTURER_NAMES]
        session.add_all(manufacturers)
        session.flush()

        categories = [
            Category(
                name=d["name"],
                slug=d["slug"],
                description=d["description"].format(equipment="industrial lift equipment"),
                criticality=d["criticality"],
            )
            for d in CATEGORY_DEFS
        ]
        session.add_all(categories)
        session.flush()
        stats.manufacturers = len(manufacturers)
        stats.categories = len(categories)

        equipment = [
            EquipmentModel(
                name=name,
                kind=kind,
                manufacturer_id=manufacturers[i % len(manufacturers)].id,
            )
            for i, (name, kind) in enumerate(EQUIPMENT_DEFS)
        ]
        session.add_all(equipment)
        session.flush()
        stats.equipment_models = len(equipment)

        suppliers = [
            Supplier(
                name=name,
                lead_time_days=int(rng.integers(5, 45)),
                reliability=round(float(rng.uniform(0.72, 0.99)), 3),
            )
            for name in SUPPLIER_NAMES
        ]
        session.add_all(suppliers)

        locations = [
            InventoryLocation(name=name, region=region) for name, region in LOCATION_DEFS
        ]
        session.add_all(locations)
        session.flush()

        documents: dict[int, list[Document]] = {}
        for category in categories:
            docs = []
            for idx, (doc_type, label) in enumerate(DOC_TYPES):
                doc = Document(
                    title=f"{category.name} {label}",
                    doc_type=doc_type,
                    category_id=category.id,
                    uri=f"synthetic://docs/{category.slug}/{doc_type}",
                    source="synthetic-corpus",
                    approved=True,
                )
                docs.append(doc)
                session.add(doc)
            documents[category.id] = docs
        session.flush()
        stats.documents = len(documents) * len(DOC_TYPES)

        # --- Parts -------------------------------------------------------
        parts_by_category: dict[int, list[Part]] = {}
        families: dict[tuple[int, int], list[Part]] = {}
        specs: list[PartSpecification] = []
        part_rows: list[dict] = []

        for cat_index, (definition, category) in enumerate(zip(CATEGORY_DEFS, categories)):
            cat_parts: list[Part] = []
            spec_doc = documents[category.id][2]
            for seq in range(PARTS_PER_CATEGORY):
                family = seq % FAMILIES_PER_CATEGORY
                manufacturer = manufacturers[int(rng.integers(0, len(manufacturers)))]
                key_values = {}
                for s_idx, spec_name in enumerate(definition["key_specs"]):
                    options = definition["spec_options"][spec_name]
                    key_values[spec_name] = options[(family + s_idx) % len(options)]

                base = f"{definition['prefix']}{1000 + cat_index * 13 + family * 37}"
                part_number = f"{base}-{seq:02d}{_mfr_code(manufacturer.name)}"
                key_summary = " / ".join(f"{k.replace('_', ' ')} {v}" for k, v in key_values.items())
                name = f"{definition['noun']} {base}"

                low, high = PRICE_RANGES[category.slug]
                price = round(float(rng.uniform(low, high)), 2)
                status = "active"
                roll = float(rng.random())
                if roll < 0.05:
                    status = "superseded"
                elif roll < 0.07:
                    status = "discontinued"

                criticality = category.criticality
                if category.criticality == "high" and float(rng.random()) < 0.3:
                    criticality = "critical"

                part = Part(
                    part_number=part_number,
                    name=name,
                    description=(
                        f"{definition['description'].format(equipment='industrial lift equipment')} "
                        f"Key specification: {key_summary}. Synthetic record."
                    ),
                    manufacturer_id=manufacturer.id,
                    category_id=category.id,
                    price=price,
                    status=status,
                    criticality=criticality,
                )
                session.add(part)
                cat_parts.append(part)
                families.setdefault((category.id, family), []).append(part)

                for spec_name, options in definition["spec_options"].items():
                    if spec_name in key_values:
                        value = key_values[spec_name]
                    else:
                        value = options[int(rng.integers(0, len(options)))]
                    unit = None
                    if spec_name.endswith("_mm"):
                        unit = "mm"
                    elif spec_name.endswith("_v"):
                        unit = "V"
                    elif spec_name.endswith("_bar"):
                        unit = "bar"
                    elif spec_name.endswith("_kg"):
                        unit = "kg"
                    elif spec_name.endswith("_a"):
                        unit = "A"
                    elif spec_name.endswith("_cc"):
                        unit = "cc/rev"
                    elif spec_name.endswith("_kn"):
                        unit = "kN"
                    specs.append(
                        PartSpecification(
                            part=part,
                            name=spec_name,
                            value=str(value),
                            unit=unit,
                            source_document_id=spec_doc.id,
                        )
                    )

                part_rows.append(
                    {
                        "part": part,
                        "category": category,
                        "definition": definition,
                        "family": family,
                        "manufacturer": manufacturer,
                    }
                )

            parts_by_category[category.id] = cat_parts

        session.flush()
        session.add_all(specs)
        session.flush()
        stats.parts = sum(len(v) for v in parts_by_category.values())
        stats.specifications = len(specs)

        # --- Supersession links -----------------------------------------
        superseded = [p for p in session.scalars(select(Part).where(Part.status == "superseded"))]
        for old in superseded:
            row = next(r for r in part_rows if r["part"].id == old.id)
            peers = [p for p in families[(old.category_id, row["family"])] if p.id != old.id]
            if peers:
                old.superseded_by_id = peers[0].id

        # --- Equipment compatibility ------------------------------------
        equipment_by_kind: dict[str, list[EquipmentModel]] = {}
        for model in equipment:
            equipment_by_kind.setdefault(model.kind, []).append(model)

        equipment_links: list[EquipmentPart] = []
        for row in part_rows:
            part = row["part"]
            kinds = CATEGORY_EQUIPMENT_KINDS.get(row["category"].slug, [])
            candidates = [m for kind in kinds for m in equipment_by_kind.get(kind, [])]
            if not candidates:
                continue
            count = 1 if float(rng.random()) < 0.6 else 2
            for model in py_rng.sample(candidates, k=min(count, len(candidates))):
                equipment_links.append(EquipmentPart(part_id=part.id, equipment_model_id=model.id))
        session.add_all(equipment_links)

        # --- Suppliers ---------------------------------------------------
        part_suppliers: list[PartSupplier] = []
        for row in part_rows:
            part = row["part"]
            chosen = py_rng.sample(suppliers, k=2)
            for supplier in chosen:
                part_suppliers.append(
                    PartSupplier(
                        part_id=part.id,
                        supplier_id=supplier.id,
                        unit_cost=round(part.price * float(rng.uniform(0.55, 0.9)), 2),
                        lead_time_days=int(supplier.lead_time_days + rng.integers(-3, 8)),
                    )
                )
        session.add_all(part_suppliers)

        # --- Compatibility edges ----------------------------------------
        compat_rows: list[Compatibility] = []
        for (category_id, family), members in families.items():
            bulletin = documents[category_id][1]
            for i, part in enumerate(members):
                peers = [m for j, m in enumerate(members) if j != i]
                py_rng.shuffle(peers)
                for peer in peers[:2]:
                    shared = sum(
                        1 for s in part.specifications if any(s.name == t.name and s.value == t.value for t in peer.specifications)
                    )
                    confidence = round(min(0.98, 0.62 + 0.07 * shared), 3)
                    compat_rows.append(
                        Compatibility(
                            part_id=part.id,
                            related_part_id=peer.id,
                            relationship="compatible",
                            confidence=confidence,
                            source="synthetic-compatibility-bulletin",
                            source_document_id=bulletin.id,
                            notes=f"Interchangeable within family {family}.",
                        )
                    )

        for old in superseded:
            if old.superseded_by_id:
                replacement = session.get(Part, old.superseded_by_id)
                if replacement:
                    doc = documents[old.category_id][1]
                    compat_rows.append(
                        Compatibility(
                            part_id=replacement.id,
                            related_part_id=old.id,
                            relationship="supersedes",
                            confidence=0.96,
                            source="synthetic-supersession-notice",
                            source_document_id=doc.id,
                            notes="Replacement supersedes the older part number.",
                        )
                    )
                    compat_rows.append(
                        Compatibility(
                            part_id=old.id,
                            related_part_id=replacement.id,
                            relationship="replaces",
                            confidence=0.9,
                            source="synthetic-supersession-notice",
                            source_document_id=doc.id,
                            notes="Older part is replaced by the newer part number.",
                        )
                    )
        session.add_all(compat_rows)
        session.flush()
        stats.compatibilities = len(compat_rows)

        # --- Document chunks --------------------------------------------
        chunk_rows: list[dict] = []
        for category in categories:
            cat_parts = parts_by_category[category.id]
            for doc in documents[category.id]:
                chunk_rows.extend(_build_chunks(doc, category, cat_parts, py_rng))
        for row in chunk_rows:
            row["token_count"] = len(row["text"].split())
        if chunk_rows:
            session.bulk_insert_mappings(DocumentChunk, chunk_rows)
        stats.chunks = len(chunk_rows)

        # --- Demand history ---------------------------------------------
        end = date.today()
        start = end - timedelta(days=DEMAND_DAYS - 1)
        dates = [start + timedelta(days=i) for i in range(DEMAND_DAYS)]
        day_index = np.arange(DEMAND_DAYS)
        month_angle = 2 * np.pi * (day_index / 365.25)
        weekday = np.array([d.weekday() for d in dates])
        weekend_factor = np.where(weekday >= 5, 0.45, 1.0)
        seasonal = 1.0 + 0.22 * np.sin(month_angle - 1.1)

        demand_rows: list[dict] = []
        for row in part_rows:
            part = row["part"]
            base_rate = float(rng.uniform(0.05, 2.4))
            if part.criticality == "critical":
                base_rate *= 1.35
            intermittent = float(rng.random()) < 0.18
            trend = np.linspace(0.85, 1.15, DEMAND_DAYS) * float(rng.uniform(0.9, 1.1))
            lam = base_rate * seasonal * weekend_factor * trend
            if intermittent:
                lam *= 0.35
                draws = rng.poisson(lam)
                mask = rng.random(DEMAND_DAYS) < 0.45
                draws = np.where(mask, 0, draws)
            else:
                draws = rng.poisson(lam)
            for d, qty in zip(dates, draws):
                demand_rows.append({"part_id": part.id, "date": d, "quantity": int(qty)})
        for i in range(0, len(demand_rows), 20000):
            session.bulk_insert_mappings(DemandHistory, demand_rows[i : i + 20000])
        stats.demand_rows = len(demand_rows)

        # --- Inventory snapshots ----------------------------------------
        inventory_rows: list[dict] = []
        monthly_dates = []
        cursor = date(end.year, end.month, 1)
        for _ in range(INVENTORY_MONTHS):
            monthly_dates.append(cursor)
            cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
        monthly_dates.reverse()

        demand_by_part: dict[int, list[int]] = {}
        for row in demand_rows:
            demand_by_part.setdefault(row["part_id"], []).append(row["quantity"])

        for row in part_rows:
            part = row["part"]
            series = demand_by_part.get(part.id, [0])
            avg_daily = float(np.mean(series))
            lead_time = 14
            for month in monthly_dates:
                qty = max(0, int(avg_daily * lead_time * float(rng.uniform(0.35, 1.9))))
                loc = locations[int(rng.integers(0, len(locations)))]
                inventory_rows.append(
                    {
                        "part_id": part.id,
                        "location_id": loc.id,
                        "quantity": qty,
                        "snapshot_date": month,
                    }
                )
        session.bulk_insert_mappings(InventorySnapshot, inventory_rows)
        stats.inventory_rows = len(inventory_rows)

        session.commit()

    return stats


def _build_chunks(
    doc: Document,
    category: Category,
    parts: list[Part],
    rng: random.Random,
) -> list[dict]:
    rows: list[dict] = []
    page = 1
    rows.append(
        {
            "document_id": doc.id,
            "ordinal": 0,
            "page": page,
            "section": "Overview",
            "text": (
                f"{doc.title}. This synthetic document covers {category.name.lower()} for "
                f"industrial lift equipment. It belongs to this repository's generated demo "
                f"dataset and does not describe real products. Always confirm fitment against the machine "
                f"serial number before ordering."
            ),
        }
    )

    by_family: dict[str, list[Part]] = {}
    for part in parts:
        key = part.part_number.rsplit("-", 1)[0]
        by_family.setdefault(key, []).append(part)

    for family_key, members in by_family.items():
        page += 1
        examples = members[:3]
        lines = []
        for part in examples:
            spec_text = ", ".join(
                f"{s.name}={s.value}{(' ' + s.unit) if s.unit else ''}"
                for s in part.specifications[:4]
            )
            lines.append(f"{part.part_number} ({part.name}) — {spec_text}")
        text = (
            f"{category.name} family {family_key}. Catalogue entries: " + "; ".join(lines) + ". "
            f"Cross-reference the part number, key dimensions and mounting pattern before "
            f"fitting. Torque values are listed in the maintenance guide."
        )
        if doc.doc_type == "compatibility_bulletin":
            text += (
                " The following part numbers are interchangeable within this family when the "
                "key specification matches: " + ", ".join(p.part_number for p in members) + "."
            )
        if doc.doc_type == "maintenance_guide":
            text += (
                " Inspection interval: every 500 operating hours. Replace at the first sign of "
                "wear, leakage or abnormal noise."
            )
        if doc.doc_type == "spec_sheet":
            text += " All values are nominal and measured at 20 degrees Celsius."
        rows.append(
            {
                "document_id": doc.id,
                "ordinal": len(rows),
                "page": page,
                "section": f"Family {family_key}",
                "text": text,
            }
        )

    page += 1
    sample = parts[:6]
    rows.append(
        {
            "document_id": doc.id,
            "ordinal": len(rows),
            "page": page,
            "section": "Compatibility Notes",
            "text": (
                f"Compatibility guidance for {category.name.lower()}: parts listed in the same "
                f"family are compatible only when bore, thread, pressure rating and mounting "
                f"match. Superseded part numbers remain listed for reference. Example part "
                f"numbers covered here include {', '.join(p.part_number for p in sample)}. "
                f"Where evidence is missing, request engineering approval instead of assuming "
                f"interchangeability."
            ),
        }
    )

    page += 1
    rows.append(
        {
            "document_id": doc.id,
            "ordinal": len(rows),
            "page": page,
            "section": "Storage and Handling",
            "text": (
                f"Store {category.name.lower()} in a dry area between 5 and 35 degrees Celsius, "
                f"away from direct sunlight. Keep protective caps fitted until installation. "
                f"Record the batch and part number in the maintenance log after replacement."
            ),
        }
    )
    return rows


def generate_images() -> int:
    """Render one synthetic PNG per part under artifacts/vision/dataset/all."""
    output = settings.artifact_path / "vision" / "dataset" / "all"
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    with Session(engine) as session:
        parts = session.scalars(select(Part).order_by(Part.id)).all()
        categories = {c.id: c for c in session.scalars(select(Category))}
        definitions = {d["slug"]: d for d in CATEGORY_DEFS}
        for part in parts:
            category = categories.get(part.category_id)
            if not category:
                continue
            definition = definitions[category.slug]
            save_part_image(
                output_dir=output,
                category_slug=category.slug,
                part_number=part.part_number,
                shape=definition["shape"],
                color=definition["color"],
                seed=part.id * 7919 + 13,
                size=256,
            )
            count += 1
    return count


def dataset_summary() -> dict:
    with Session(engine) as session:
        return {
            "parts": session.query(Part).count(),
            "manufacturers": session.query(Manufacturer).count(),
            "categories": session.query(Category).count(),
            "documents": session.query(Document).count(),
            "chunks": session.query(DocumentChunk).count(),
            "demand_rows": session.query(DemandHistory).count(),
            "inventory_rows": session.query(InventorySnapshot).count(),
            "compatibilities": session.query(Compatibility).count(),
        }
