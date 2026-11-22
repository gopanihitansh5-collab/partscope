from __future__ import annotations

import hashlib
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.config import settings
from src.models import Part
from src.schemas.vision import (
    SimilarImageMatch,
    SimilarImageResponse,
    VisionCandidate,
    VisionIdentifyResponse,
)
from src.vision.model import VisionBaseline

_model_cache: dict[str, tuple[float, VisionBaseline]] = {}


def artifact_dir() -> Path:
    return settings.artifact_path / "vision" / "baseline"


def load_model() -> VisionBaseline:
    directory = artifact_dir()
    key = str(directory)
    mtime = (directory / "embeddings.npz").stat().st_mtime if (directory / "embeddings.npz").exists() else 0.0
    cached = _model_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    model = VisionBaseline.load(directory)
    _model_cache[key] = (mtime, model)
    return model


def invalidate_cache() -> None:
    _model_cache.clear()


def open_image(path: Path) -> Image.Image:
    try:
        image = Image.open(path)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Unreadable image: {exc}") from exc
    return image.convert("RGB")


def image_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identify(session: Session, path: Path, top_k: int | None = None) -> VisionIdentifyResponse:
    started = time.perf_counter()
    model = load_model()
    image = open_image(path)
    candidates = model.predict(image, top_k=top_k or settings.vision_top_k)

    part_numbers = [c.part_number for c in candidates]
    parts = {
        p.part_number: p
        for p in session.scalars(select(Part).where(Part.part_number.in_(part_numbers)))
    }

    out: list[VisionCandidate] = []
    for rank, cand in enumerate(candidates, start=1):
        part = parts.get(cand.part_number)
        out.append(
            VisionCandidate(
                label=cand.label,
                part_id=part.id if part else None,
                part_number=cand.part_number,
                category=cand.category,
                score=cand.score,
                rank=rank,
            )
        )

    confidence = out[0].score if out else 0.0
    low_confidence = confidence < 0.45
    warnings = [
        "Baseline trained on procedurally generated synthetic renders. "
        "Real photographs may not match; treat results as a pipeline demonstration."
    ]
    if low_confidence:
        warnings.append("Low confidence: route this image to manual review.")

    return VisionIdentifyResponse(
        model_name=model.name,
        model_version=model.version,
        runtime=model.runtime,
        precision=model.precision,
        image_hash=image_hash(path),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        top_candidates=out,
        confidence=confidence,
        low_confidence=low_confidence,
        review_required=low_confidence,
        warnings=warnings,
    )


def similar(session: Session, path: Path, top_k: int = 5) -> SimilarImageResponse:
    started = time.perf_counter()
    model = load_model()
    image = open_image(path)
    candidates = model.predict(image, top_k=top_k)
    part_numbers = [c.part_number for c in candidates]
    parts = {
        p.part_number: p
        for p in session.scalars(select(Part).where(Part.part_number.in_(part_numbers)))
    }
    matches = [
        SimilarImageMatch(
            part_id=parts[c.part_number].id if c.part_number in parts else None,
            part_number=c.part_number,
            label=c.label,
            similarity=c.score,
        )
        for c in candidates
    ]
    return SimilarImageResponse(
        model_name=model.name,
        model_version=model.version,
        matches=matches,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
