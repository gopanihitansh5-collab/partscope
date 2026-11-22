from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
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


def evaluate_holdout(session: Session, top_k: int = 5) -> dict:
    import json
    import statistics

    from sklearn.metrics import f1_score, recall_score

    model = load_model()
    dataset_dir = settings.artifact_path / "vision" / "dataset" / "all"
    if not dataset_dir.exists():
        raise ValueError("Vision dataset not found. Run the seed script first.")

    y_true: list[str] = []
    y_pred: list[str] = []
    top5_hits = 0
    latencies: list[float] = []
    per_class_correct: dict[str, int] = {}
    per_class_total: dict[str, int] = {}

    for path in sorted(dataset_dir.glob("*/*.png")):
        category = path.parent.name
        if int(hashlib.sha256(path.stem.encode()).hexdigest()[:8], 16) % 5 != 0:
            continue
        started = time.perf_counter()
        candidates = model.predict(open_image(path), top_k=max(top_k, 5))
        latencies.append((time.perf_counter() - started) * 1000)

        predicted = candidates[0].category if candidates else "unknown"
        y_true.append(category)
        y_pred.append(predicted)
        per_class_total[category] = per_class_total.get(category, 0) + 1
        if predicted == category:
            per_class_correct[category] = per_class_correct.get(category, 0) + 1
        if any(c.category == category for c in candidates[:5]):
            top5_hits += 1

    if not y_true:
        raise ValueError("No held-out images found. Run the seed script first.")

    samples = len(y_true)
    report = {
        "dataset": "synthetic renders, 20% held out by part hash",
        "samples": samples,
        "top1_accuracy": round(sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == p) / samples, 4),
        "top5_accuracy": round(top5_hits / samples, 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "per_class_recall": {
            label: round(float(value), 4)
            for label, value in zip(
                sorted(per_class_total),
                recall_score(
                    y_true,
                    y_pred,
                    labels=sorted(per_class_total),
                    average=None,
                    zero_division=0,
                ), strict=False,
            )
        },
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(
            sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0.0, 2
        ),
        "model_name": model.name,
        "model_version": model.version,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    report_dir = settings.artifact_path.parent / "evaluation" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "vision_eval.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report


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
