"""Deterministic image descriptor used by the CPU baseline.

The descriptor is intentionally simple and fully documented: HSV colour
histograms, gradient statistics and coarse spatial layout. It is a legitimate
baseline that a CNN/ONNX runner can replace behind the same interface. It is
not claimed to be state of the art.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _hsv_histograms(arr: np.ndarray, bins: int = 8) -> np.ndarray:
    """Vectorised RGB->HSV conversion followed by per-channel histograms."""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    maxc = arr.max(axis=-1)
    minc = arr.min(axis=-1)
    delta = maxc - minc

    hue = np.zeros_like(maxc)
    nonzero = delta > 1e-6
    rmask = nonzero & (maxc == r)
    gmask = nonzero & (maxc == g) & ~rmask
    bmask = nonzero & ~rmask & ~gmask
    hue[rmask] = ((g[rmask] - b[rmask]) / delta[rmask]) % 6.0
    hue[gmask] = (b[gmask] - r[gmask]) / delta[gmask] + 2.0
    hue[bmask] = (r[bmask] - g[bmask]) / delta[bmask] + 4.0
    hue /= 6.0

    sat = np.where(maxc > 1e-6, delta / np.maximum(maxc, 1e-6), 0.0)

    feats = []
    for channel in (hue, sat, maxc):
        hist, _ = np.histogram(channel, bins=bins, range=(0.0, 1.0), density=True)
        feats.append(hist.astype(np.float32))
    return np.concatenate(feats)


def _gradient_features(gray: np.ndarray) -> np.ndarray:
    gx = np.diff(gray, axis=1, prepend=gray[:, :1])
    gy = np.diff(gray, axis=0, prepend=gray[:1, :])
    mag = np.sqrt(gx**2 + gy**2)
    ang = np.arctan2(gy, gx)

    orientation_hist, _ = np.histogram(ang, bins=8, range=(-np.pi, np.pi), weights=mag)
    orientation_hist = orientation_hist / (orientation_hist.sum() + 1e-8)

    edge_density = float((mag > 0.08).mean())
    stats = np.array(
        [
            float(mag.mean()),
            float(mag.std()),
            float(np.percentile(mag, 90)),
            edge_density,
        ],
        dtype=np.float32,
    )
    return np.concatenate([orientation_hist.astype(np.float32), stats])


def _spatial_features(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    quadrants = [
        gray[: h // 2, : w // 2],
        gray[: h // 2, w // 2 :],
        gray[h // 2 :, : w // 2],
        gray[h // 2 :, w // 2 :],
    ]
    feats = [float(q.mean()) for q in quadrants]
    feats.append(float(gray.mean()))
    feats.append(float(gray.std()))
    ys, xs = np.nonzero(gray < 0.55)
    if len(xs) > 0:
        feats.extend(
            [
                float(xs.mean() / w),
                float(ys.mean() / h),
                float(len(xs) / (h * w)),
                float(xs.std() / w),
                float(ys.std() / h),
            ]
        )
    else:
        feats.extend([0.5, 0.5, 0.0, 0.0, 0.0])
    return np.array(feats, dtype=np.float32)


def extract_features(image: Image.Image, size: int = 64) -> np.ndarray:
    """Return an L2-normalised float32 descriptor for an RGB image."""
    image = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    arr = np.asarray(image, dtype=np.float32) / 255.0
    gray = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]).astype(np.float32)

    colour = _hsv_histograms(arr)
    gradient = _gradient_features(gray)
    spatial = _spatial_features(gray)

    feats = np.concatenate([colour, gradient, spatial]).astype(np.float32)
    norm = float(np.linalg.norm(feats)) + 1e-8
    return feats / norm
