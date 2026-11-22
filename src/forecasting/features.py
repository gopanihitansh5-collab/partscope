"""Leakage-safe feature engineering for 30-day demand forecasting."""

from __future__ import annotations

import math
from datetime import date

import numpy as np

HORIZON = 30
MIN_HISTORY = 120
ORIGIN_STRIDE = 7
CATEGORY_SLUGS = [
    "bearings",
    "filters",
    "drive-belts",
    "hydraulic-pumps",
    "hydraulic-hoses",
    "electrical-relays",
    "brake-pads",
    "wheels-tires",
    "seals-gaskets",
    "fasteners",
    "transmission-gears",
    "cooling-fans",
    "lighting",
    "sensors",
    "cabin-seats",
]

BASE_FEATURES = [
    "last_7_sum",
    "last_14_sum",
    "last_30_sum",
    "last_90_avg_month",
    "mean_7",
    "mean_14",
    "mean_30",
    "std_30",
    "trend_14",
    "zero_ratio_30",
    "season_sin",
    "season_cos",
    "month_sin",
    "month_cos",
    "criticality_score",
]


def feature_names() -> list[str]:
    return BASE_FEATURES + [f"cat_{slug}" for slug in CATEGORY_SLUGS]


def make_features(
    series: np.ndarray,
    origin_index: int,
    origin_date: date,
    category_slug: str,
    criticality: str,
) -> dict[str, float]:
    """Features computed strictly from ``series[: origin_index + 1]``."""
    history = series[: origin_index + 1]
    last_7 = float(history[-7:].sum())
    last_14 = float(history[-14:].sum())
    last_30 = float(history[-30:].sum())
    last_90 = float(history[-90:].sum())
    mean_7 = float(history[-7:].mean())
    mean_14 = float(history[-14:].mean())
    mean_30 = float(history[-30:].mean())
    std_30 = float(history[-30:].std())
    prev_14 = float(history[-28:-14].mean()) if len(history) >= 28 else mean_14
    trend_14 = mean_14 / (prev_14 + 1e-6)
    zero_ratio_30 = float((history[-30:] == 0).mean())

    day_of_year = origin_date.timetuple().tm_yday
    season_sin = math.sin(2 * math.pi * day_of_year / 365.25)
    season_cos = math.cos(2 * math.pi * day_of_year / 365.25)
    month_sin = math.sin(2 * math.pi * origin_date.month / 12)
    month_cos = math.cos(2 * math.pi * origin_date.month / 12)

    criticality_score = {"critical": 1.0, "high": 0.6, "standard": 0.2}.get(criticality, 0.2)

    features = {
        "last_7_sum": last_7,
        "last_14_sum": last_14,
        "last_30_sum": last_30,
        "last_90_avg_month": last_90 / 3.0,
        "mean_7": mean_7,
        "mean_14": mean_14,
        "mean_30": mean_30,
        "std_30": std_30,
        "trend_14": trend_14,
        "zero_ratio_30": zero_ratio_30,
        "season_sin": season_sin,
        "season_cos": season_cos,
        "month_sin": month_sin,
        "month_cos": month_cos,
        "criticality_score": criticality_score,
    }
    for slug in CATEGORY_SLUGS:
        features[f"cat_{slug}"] = 1.0 if slug == category_slug else 0.0
    return features


def to_vector(features: dict[str, float]) -> list[float]:
    names = feature_names()
    return [float(features.get(name, 0.0)) for name in names]
