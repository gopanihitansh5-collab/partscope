"""Forecast model artifact, explainability and baseline definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from src.forecasting.features import feature_names


class ForecastArtifactNotFound(RuntimeError):
    pass


def build_estimator() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.06,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=42,
    )


@dataclass
class ForecastModel:
    pipeline: HistGradientBoostingRegressor
    residual_std: float
    feature_medians: list[float] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    name: str = "demand-hgb-baseline"
    version: str = "0.1.0"
    trained_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    train_rows: int = 0
    test_rows: int = 0
    train_range: list[str] = field(default_factory=list)
    test_range: list[str] = field(default_factory=list)
    dataset_hash: str = ""
    horizon: int = 30

    def predict(self, features: list[float], horizon_days: int = 30) -> tuple[float, float]:
        x = np.asarray([features], dtype=float)
        raw = max(0.0, float(self.pipeline.predict(x)[0]))
        sigma = self.residual_std * float(np.sqrt(max(horizon_days / self.horizon, 0.0)))
        expected = raw * (horizon_days / self.horizon)
        return max(0.0, expected), sigma

    def drivers(self, features: list[float], top_n: int = 4) -> list[dict]:
        """Local sensitivity: move each feature to the training median.

        This is a counterfactual explanation, not a SHAP value. It is cheap,
        deterministic and honest about what it measures.
        """
        if not self.feature_medians:
            return []
        x = np.asarray(features, dtype=float)
        median = np.asarray(self.feature_medians, dtype=float)
        base = float(self.pipeline.predict(x.reshape(1, -1))[0])
        names = feature_names()
        contributions = []
        for i in range(len(x)):
            counterfactual = x.copy()
            counterfactual[i] = median[i]
            delta = base - float(self.pipeline.predict(counterfactual.reshape(1, -1))[0])
            contributions.append((abs(delta), delta, names[i]))
        contributions.sort(key=lambda item: -item[0])
        return [
            {
                "feature": name,
                "impact": round(delta, 4),
                "direction": "raises demand" if delta >= 0 else "lowers demand",
            }
            for _, delta, name in contributions[:top_n]
        ]

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, directory / "model.joblib")
        meta = {
            "name": self.name,
            "version": self.version,
            "runtime": "scikit-learn",
            "precision": "fp64",
            "trained_at": self.trained_at,
            "horizon_days": self.horizon,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "train_range": self.train_range,
            "test_range": self.test_range,
            "dataset_hash": self.dataset_hash,
            "residual_std": round(self.residual_std, 4),
            "feature_medians": [round(v, 6) for v in self.feature_medians],
            "metrics": self.metrics,
            "features": feature_names(),
            "notes": (
                "Gradient-boosted tabular regressor on leakage-safe lag/rolling/seasonal "
                "features. A seasonal-naive baseline is reported alongside. Intervals use "
                "the validation residual standard deviation. Per-part drivers are local "
                "counterfactual-to-median sensitivities."
            ),
        }
        (directory / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return directory

    @classmethod
    def load(cls, directory: Path) -> ForecastModel:
        model_path = directory / "model.joblib"
        meta_path = directory / "metadata.json"
        if not model_path.exists() or not meta_path.exists():
            raise ForecastArtifactNotFound(
                f"Forecast artifact missing at {directory}. Run "
                "`python -m training.forecasting.train` before calling the forecast API."
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return cls(
            pipeline=joblib.load(model_path),
            residual_std=float(meta.get("residual_std", 1.0)),
            feature_medians=[float(v) for v in meta.get("feature_medians", [])],
            metrics=meta.get("metrics", {}),
            name=meta.get("name", "demand-hgb-baseline"),
            version=meta.get("version", "0.1.0"),
            trained_at=meta.get("trained_at", ""),
            train_rows=int(meta.get("train_rows", 0)),
            test_rows=int(meta.get("test_rows", 0)),
            train_range=meta.get("train_range", []),
            test_range=meta.get("test_range", []),
            dataset_hash=meta.get("dataset_hash", ""),
            horizon=int(meta.get("horizon_days", 30)),
        )
