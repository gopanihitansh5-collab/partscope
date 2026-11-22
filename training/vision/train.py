"""Train and register the CPU vision baseline on the synthetic renders."""

from __future__ import annotations

import hashlib
import json
import statistics
import time

import numpy as np
from sklearn.metrics import f1_score, recall_score
from sqlalchemy import select

from src.common.config import settings
from src.common.db import SessionLocal, init_db
from src.common.logging import get_logger
from src.models import Category, ModelVersion, Part
from src.vision.features import extract_features
from src.vision.model import VisionBaseline
from src.vision.service import invalidate_cache, open_image

log = get_logger("training.vision")


def main() -> None:
    started = time.perf_counter()
    init_db()
    dataset_dir = settings.artifact_path / "vision" / "dataset" / "all"
    if not dataset_dir.exists():
        raise SystemExit("Dataset not found. Run `python -m scripts.seed` first.")

    with SessionLocal() as session:
        categories = {c.id: c for c in session.scalars(select(Category))}
        parts = list(session.scalars(select(Part).order_by(Part.id)))
        if not parts:
            raise SystemExit("No parts in the database. Run the seed script first.")

        train_rows: list[tuple[np.ndarray, Part, str]] = []
        test_rows: list[tuple[np.ndarray, Part, str]] = []
        missing = 0

        for part in parts:
            category = categories.get(part.category_id)
            if category is None:
                continue
            path = dataset_dir / category.slug / f"{part.part_number}.png"
            if not path.exists():
                missing += 1
                continue
            features = extract_features(open_image(path), size=settings.vision_image_size)
            bucket = (
                test_rows
                if int(hashlib.sha256(path.stem.encode()).hexdigest()[:8], 16) % 5 == 0
                else train_rows
            )
            bucket.append((features, part, category.slug))

        if len(train_rows) < 50 or len(test_rows) < 10:
            raise SystemExit("Not enough images for a train/test split.")

        embeddings = np.vstack([row[0] for row in train_rows]).astype(np.float32)
        model = VisionBaseline(
            embeddings=embeddings,
            part_numbers=[row[1].part_number for row in train_rows],
            labels=[row[1].name for row in train_rows],
            categories=[row[2] for row in train_rows],
            image_size=settings.vision_image_size,
            version=f"0.1.{int(time.time()) % 100000}",
            metadata={
                "dataset_uri": str(dataset_dir),
                "dataset_hash": hashlib.sha256(
                    "|".join(sorted(row[1].part_number for row in train_rows)).encode()
                ).hexdigest()[:16],
                "train_size": len(train_rows),
                "test_size": len(test_rows),
                "missing_images": missing,
            },
        )

        y_true: list[str] = []
        y_pred: list[str] = []
        top5_hits = 0
        latencies: list[float] = []
        for features, part, category_slug in test_rows:
            sims = embeddings @ features
            k = min(15, len(sims))
            top_idx = np.argpartition(-sims, k - 1)[:k]
            top_idx = top_idx[np.argsort(-sims[top_idx])]
            predicted = model.categories[int(top_idx[0])]
            y_true.append(category_slug)
            y_pred.append(predicted)
            if any(model.categories[int(i)] == category_slug for i in top_idx[:5]):
                top5_hits += 1
            started_infer = time.perf_counter()
            model.predict(open_image(dataset_dir / category_slug / f"{part.part_number}.png"))
            latencies.append((time.perf_counter() - started_infer) * 1000)

        labels = sorted(set(y_true))
        metrics = {
            "top1_accuracy": round(sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == p) / len(y_true), 4),
            "top5_accuracy": round(top5_hits / len(y_true), 4),
            "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
            "per_class_recall": {
                label: round(float(value), 4)
                for label, value in zip(
                    labels,
                    recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0), strict=False,
                )
            },
            "latency_ms_p50": round(statistics.median(latencies), 2),
            "latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 2),
            "samples": len(y_true),
            "split": "20% held out by part hash",
        }
        model.metadata["metrics"] = metrics
        model.save(settings.artifact_path / "vision" / "baseline")
        invalidate_cache()

        session.add(
            ModelVersion(
                name=model.name,
                version=model.version,
                task="classification",
                runtime=model.runtime,
                precision=model.precision,
                artifact_uri=str(settings.artifact_path / "vision" / "baseline"),
                dataset_uri=str(dataset_dir),
                dataset_hash=model.metadata["dataset_hash"],
                metrics=metrics,
                params={
                    "descriptor": "hsv-histogram + gradient-orientation + spatial",
                    "descriptor_dim": int(embeddings.shape[1]),
                    "knn_k": 15,
                    "train_size": len(train_rows),
                    "test_size": len(test_rows),
                    "train_seconds": round(time.perf_counter() - started, 2),
                },
                approved=True,
                notes="CPU baseline trained on procedurally generated synthetic renders.",
            )
        )
        session.commit()

        report_dir = settings.artifact_path.parent / "evaluation" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "vision_training.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
