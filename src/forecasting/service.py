"""Demand forecasting: training, inference, risk scoring and evaluation."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.config import settings
from src.common.utils import clamp, stable_hash, utcnow
from src.forecasting.features import (
    HORIZON,
    MIN_HISTORY,
    ORIGIN_STRIDE,
    make_features,
    to_vector,
)
from src.forecasting.model import ForecastModel, build_estimator
from src.models import (
    Category,
    DemandHistory,
    InventorySnapshot,
    ModelVersion,
    Part,
    Prediction,
)
from src.schemas.forecast import ForecastDriver, ForecastResponse

_model_cache: dict[str, tuple[float, ForecastModel]] = {}
_demand_cache: dict[str, tuple[tuple[int, str], dict[int, np.ndarray], list[date]]] = {}


def model_dir() -> Path:
    return settings.artifact_path / "forecasting"


def _load_demand(session: Session) -> tuple[dict[int, np.ndarray], list[date]]:
    from sqlalchemy import func

    count, max_date = session.execute(
        select(func.count(DemandHistory.id), func.max(DemandHistory.date))
    ).one()
    signature = (int(count), str(max_date))
    key = settings.database_url
    cached = _demand_cache.get(key)
    if cached and cached[0] == signature:
        return cached[1], cached[2]

    rows = session.execute(
        select(DemandHistory.part_id, DemandHistory.date, DemandHistory.quantity).order_by(
            DemandHistory.part_id, DemandHistory.date
        )
    ).all()
    if not rows:
        raise ValueError("No demand history. Run the seed script first.")

    dates = sorted({row[1] for row in rows})
    date_index = {d: i for i, d in enumerate(dates)}
    series: dict[int, np.ndarray] = {}
    for part_id, d, qty in rows:
        arr = series.get(part_id)
        if arr is None:
            arr = np.zeros(len(dates), dtype=float)
            series[part_id] = arr
        arr[date_index[d]] = float(qty)
    _demand_cache[key] = (signature, series, dates)
    return series, dates


def _part_meta(session: Session) -> dict[int, dict]:
    rows = session.execute(
        select(Part.id, Part.criticality, Category.slug).outerjoin(
            Category, Part.category_id == Category.id
        )
    ).all()
    return {
        part_id: {"criticality": criticality, "category_slug": slug or "bearings"}
        for part_id, criticality, slug in rows
    }


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    origin_dates: list[date]
    part_ids: list[int]


def _build_dataset(series: dict[int, np.ndarray], dates: list[date], meta: dict[int, dict]) -> Dataset:
    rows_x: list[list[float]] = []
    rows_y: list[float] = []
    origins: list[date] = []
    part_ids: list[int] = []

    for part_id, values in series.items():
        if len(values) < MIN_HISTORY + HORIZON + 1:
            continue
        part_meta = meta.get(part_id, {"criticality": "standard", "category_slug": "bearings"})
        for origin in range(MIN_HISTORY, len(values) - HORIZON, ORIGIN_STRIDE):
            target = float(values[origin + 1 : origin + 1 + HORIZON].sum())
            features = make_features(
                values,
                origin,
                dates[origin],
                part_meta["category_slug"],
                part_meta["criticality"],
            )
            rows_x.append(to_vector(features))
            rows_y.append(target)
            origins.append(dates[origin])
            part_ids.append(part_id)

    return Dataset(
        X=np.asarray(rows_x, dtype=float),
        y=np.asarray(rows_y, dtype=float),
        origin_dates=origins,
        part_ids=part_ids,
    )


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_pred = np.clip(y_pred, 0, None)
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    mask = y_true > 0
    mape = float(np.mean(np.abs(errors[mask] / y_true[mask])) * 100) if mask.any() else 0.0
    bias = float(np.mean(errors))
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4),
        "bias": round(bias, 4),
        "samples": int(len(y_true)),
    }


def train(session: Session) -> ForecastModel:
    started = time.perf_counter()
    series, dates = _load_demand(session)
    meta = _part_meta(session)
    dataset = _build_dataset(series, dates, meta)
    if len(dataset.y) < 200:
        raise ValueError("Not enough demand samples to train a forecast model.")

    end = dates[-1]
    test_start = end - timedelta(days=60)
    calib_start = end - timedelta(days=120)

    train_mask = np.array([d < calib_start for d in dataset.origin_dates])
    calib_mask = np.array([calib_start <= d < test_start for d in dataset.origin_dates])
    test_mask = np.array([d >= test_start for d in dataset.origin_dates])

    if not train_mask.any() or not calib_mask.any() or not test_mask.any():
        raise ValueError("Time-based split produced an empty partition; extend demand history.")

    pipeline = build_estimator()
    pipeline.fit(dataset.X[train_mask], dataset.y[train_mask])

    calib_pred = np.clip(pipeline.predict(dataset.X[calib_mask]), 0, None)
    residual_std = float(np.std(dataset.y[calib_mask] - calib_pred)) or 1.0

    test_pred = np.clip(pipeline.predict(dataset.X[test_mask]), 0, None)
    test_true = dataset.y[test_mask]

    naive_pred = np.array(
        [
            float(series[part_id][max(0, i - HORIZON) : i].sum())
            for part_id, i in _origin_indices(series, dates, dataset, test_mask)
        ]
    )
    naive_metrics = _metrics(test_true, naive_pred)
    model_metrics = _metrics(test_true, test_pred)

    z = 1.2816
    lower = np.clip(test_pred - z * residual_std, 0, None)
    upper = test_pred + z * residual_std
    coverage = float(np.mean((test_true >= lower) & (test_true <= upper)))

    improvement = 0.0
    if naive_metrics["mae"] > 0:
        improvement = (naive_metrics["mae"] - model_metrics["mae"]) / naive_metrics["mae"] * 100

    dataset_hash = stable_hash(
        f"{len(series)}:{len(dataset.y)}:{dates[0].isoformat()}:{dates[-1].isoformat()}"
    )
    feature_medians = np.median(dataset.X[train_mask], axis=0).tolist()
    model = ForecastModel(
        pipeline=pipeline,
        residual_std=residual_std,
        feature_medians=feature_medians,
        metrics={
            "model": model_metrics,
            "seasonal_naive": naive_metrics,
            "improvement_mae_pct": round(improvement, 2),
            "interval_coverage_80": round(coverage, 4),
            "split": "time-based (fit < calib < test)",
        },
        version=f"0.1.{int(time.time()) % 100000}",
        train_rows=int(train_mask.sum()),
        test_rows=int(test_mask.sum()),
        train_range=[dates[0].isoformat(), calib_start.isoformat()],
        test_range=[test_start.isoformat(), end.isoformat()],
        dataset_hash=dataset_hash,
    )
    model.save(model_dir())
    _model_cache.clear()

    session.add(
        ModelVersion(
            name=model.name,
            version=model.version,
            task="forecast",
            runtime="scikit-learn",
            precision="fp64",
            artifact_uri=str(model_dir()),
            dataset_uri="demand_history",
            dataset_hash=dataset_hash,
            metrics=model.metrics,
            params={
                "model_type": "HistGradientBoostingRegressor",
                "max_iter": 300,
                "learning_rate": 0.06,
                "horizon_days": HORIZON,
                "train_rows": model.train_rows,
                "test_rows": model.test_rows,
                "residual_std": round(residual_std, 4),
                "train_seconds": round(time.perf_counter() - started, 2),
            },
            approved=True,
        )
    )
    session.commit()
    return model


def _origin_indices(series, dates, dataset: Dataset, mask: np.ndarray):
    date_index = {d: i for i, d in enumerate(dates)}
    for part_id, origin_date, keep in zip(dataset.part_ids, dataset.origin_dates, mask, strict=False):
        if keep:
            yield part_id, date_index[origin_date] + 1


def load_model() -> ForecastModel:
    directory = model_dir()
    key = str(directory)
    path = directory / "model.joblib"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    cached = _model_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    model = ForecastModel.load(directory)
    _model_cache[key] = (mtime, model)
    return model


def _latest_stock(session: Session, part_id: int) -> tuple[float, date | None]:
    rows = session.execute(
        select(InventorySnapshot.quantity, InventorySnapshot.snapshot_date)
        .where(InventorySnapshot.part_id == part_id)
        .order_by(InventorySnapshot.snapshot_date.desc())
    ).all()
    if not rows:
        return 0.0, None
    latest_date = rows[0][1]
    total = sum(qty for qty, d in rows if d == latest_date)
    return float(total), latest_date


def forecast_part(session: Session, part_id: int, horizon_days: int = 30) -> ForecastResponse:
    part = session.get(Part, part_id)
    if part is None:
        raise ValueError(f"Part {part_id} not found.")

    model = load_model()
    series, dates = _load_demand(session)
    values = series.get(part_id)
    if values is None or len(values) < MIN_HISTORY:
        raise ValueError(f"Part {part_id} does not have enough demand history to forecast.")

    origin = len(values) - 1
    features = make_features(
        values,
        origin,
        dates[origin],
        part.category.slug if part.category else "bearings",
        part.criticality,
    )
    vector = to_vector(features)
    expected, sigma = model.predict(vector, horizon_days=horizon_days)
    sigma = max(sigma, 0.5)

    stock, snapshot_date = _latest_stock(session, part_id)
    shortage_probability = 1.0 - _normal_cdf((stock - expected) / sigma)
    predicted_stock = stock - expected
    safety = 1.2816 * sigma
    reorder = max(0.0, expected + safety - stock)

    if shortage_probability >= 0.6:
        risk = "high"
    elif shortage_probability >= 0.3:
        risk = "medium"
    else:
        risk = "low"

    warnings: list[str] = []
    zero_ratio = float((values[-30:] == 0).mean())
    if zero_ratio > 0.5:
        warnings.append("Intermittent demand: more than half of the last 30 days had zero demand.")
    if sigma > expected:
        warnings.append("Forecast uncertainty is high relative to expected demand.")
    if stock == 0:
        warnings.append("No inventory snapshot found; stock figures may be incomplete.")
    if horizon_days != model.horizon:
        warnings.append(
            f"Model was trained on a {model.horizon}-day horizon; {horizon_days}-day output is "
            "scaled and less reliable."
        )

    drivers = [
        ForecastDriver(**driver) for driver in model.drivers(vector, top_n=4)
    ]

    session.add(
        Prediction(
            part_id=part_id,
            horizon_days=horizon_days,
            expected_demand=round(expected, 3),
            lower_bound=round(max(0.0, expected - safety), 3),
            upper_bound=round(expected + safety, 3),
            shortage_probability=round(clamp(shortage_probability), 4),
            current_stock=stock,
            predicted_stock=round(predicted_stock, 3),
            reorder_quantity=round(reorder, 3),
            features={k: round(v, 4) for k, v in features.items()},
        )
    )
    session.commit()

    return ForecastResponse(
        part_id=part.id,
        part_number=part.part_number,
        part_name=part.name,
        horizon_days=horizon_days,
        expected_demand=round(expected, 2),
        lower_bound=round(max(0.0, expected - safety), 2),
        upper_bound=round(expected + safety, 2),
        current_stock=stock,
        predicted_stock=round(predicted_stock, 2),
        shortage_probability=round(clamp(shortage_probability), 4),
        reorder_quantity=round(reorder, 2),
        risk_level=risk,
        model_name=model.name,
        model_version=model.version,
        metrics=model.metrics,
        drivers=drivers,
        data_freshness=snapshot_date or dates[-1],
        warnings=warnings,
    )


def evaluate(session: Session) -> dict:
    model = load_model()
    series, dates = _load_demand(session)
    meta = _part_meta(session)
    dataset = _build_dataset(series, dates, meta)
    end = dates[-1]
    test_start = end - timedelta(days=60)
    test_mask = np.array([d >= test_start for d in dataset.origin_dates])
    if not test_mask.any():
        raise ValueError("No test samples available.")

    pred = np.clip(model.pipeline.predict(dataset.X[test_mask]), 0, None)
    true = dataset.y[test_mask]
    naive = np.array(
        [
            float(series[part_id][max(0, i - HORIZON) : i].sum())
            for part_id, i in _origin_indices(series, dates, dataset, test_mask)
        ]
    )

    z = 1.2816
    lower = np.clip(pred - z * model.residual_std, 0, None)
    upper = pred + z * model.residual_std
    coverage = float(np.mean((true >= lower) & (true <= upper)))

    model_metrics = _metrics(true, pred)
    naive_metrics = _metrics(true, naive)
    improvement = (
        (naive_metrics["mae"] - model_metrics["mae"]) / naive_metrics["mae"] * 100
        if naive_metrics["mae"] > 0
        else 0.0
    )

    report = {
        "model_name": model.name,
        "model_version": model.version,
        "model_metrics": model_metrics,
        "baseline_metrics": naive_metrics,
        "improvement": {"mae_pct": round(improvement, 2)},
        "calibration": {
            "interval": "80%",
            "coverage": round(coverage, 4),
            "residual_std": round(model.residual_std, 4),
        },
        "generated_at": utcnow().isoformat(),
        "dataset_hash": model.dataset_hash,
    }
    report_dir = settings.artifact_path.parent / "evaluation" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "forecast_eval.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))
