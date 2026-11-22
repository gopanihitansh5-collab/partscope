"""Procedural renders of synthetic parts.

These images exist so the vision pipeline can be trained and evaluated without
using any proprietary or scraped imagery. They are stylised renders, not
photographs, and the model trained on them must be presented as a pipeline
demonstrator rather than a production recogniser.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def _jitter(color: tuple[int, int, int], rng: random.Random, amount: int = 26) -> tuple[int, int, int]:
    return tuple(max(0, min(255, c + rng.randint(-amount, amount))) for c in color)  # type: ignore[return-value]


def _background(rng: random.Random, size: int) -> Image.Image:
    base = rng.randint(210, 245)
    img = Image.new("RGB", (size, size), (base, base - rng.randint(0, 6), base - rng.randint(0, 10)))
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 8)):
        x0 = rng.randint(0, size)
        y0 = rng.randint(0, size)
        r = rng.randint(size // 10, size // 3)
        shade = rng.randint(-12, 12)
        draw.ellipse(
            [x0 - r, y0 - r, x0 + r, y0 + r],
            fill=(base + shade, base + shade, base + shade),
        )
    return img.filter(ImageFilter.GaussianBlur(radius=2))


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str, color: tuple[int, int, int], size: int, rng: random.Random) -> None:
    cx, cy = size // 2, size // 2
    s = int(size * 0.62)
    half = s // 2
    dark = tuple(max(0, c - 45) for c in color)
    light = tuple(min(255, c + 40) for c in color)

    if shape == "ring":
        outer = [cx - half, cy - half, cx + half, cy + half]
        draw.ellipse(outer, fill=dark)
        draw.ellipse([cx - half + 6, cy - half + 6, cx + half - 6, cy + half - 6], fill=color)
        inner = int(half * 0.45)
        draw.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=(235, 235, 235))
        draw.arc(outer, 200, 320, fill=light, width=4)
    elif shape == "cylinder":
        w = int(s * 0.55)
        draw.rounded_rectangle([cx - w // 2, cy - half, cx + w // 2, cy + half], radius=10, fill=color)
        draw.ellipse([cx - w // 2, cy - half - 12, cx + w // 2, cy - half + 16], fill=light)
        for i in range(3):
            y = cy - half + 30 + i * (s // 4)
            draw.line([cx - w // 2 + 6, y, cx + w // 2 - 6, y], fill=dark, width=4)
    elif shape == "belt":
        draw.ellipse([cx - half, cy - int(half * 0.62), cx + half, cy + int(half * 0.62)], outline=color, width=22)
        draw.arc([cx - half, cy - int(half * 0.62), cx + half, cy + int(half * 0.62)], 210, 330, fill=light, width=3)
    elif shape == "block":
        pts = [
            (cx - half, cy - half + 18),
            (cx - half + 18, cy - half),
            (cx + half, cy - half + 10),
            (cx + half - 10, cy + half),
            (cx - half + 8, cy + half - 6),
        ]
        draw.polygon(pts, fill=color, outline=dark)
        draw.rectangle([cx - half + 22, cy - half + 34, cx + half - 30, cy + half - 26], outline=dark, width=3)
        draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=dark)
    elif shape == "tube":
        draw.line([cx - half, cy + half // 2, cx, cy - half, cx + half, cy + half // 2], fill=color, width=26, joint="curve")
        draw.line([cx - half, cy + half // 2, cx, cy - half, cx + half, cy + half // 2], fill=light, width=6, joint="curve")
        draw.rectangle([cx - half - 8, cy + half // 2 - 12, cx - half + 16, cy + half // 2 + 12], fill=dark)
    elif shape == "box":
        draw.rounded_rectangle([cx - half, cy - half, cx + half, cy + half], radius=14, fill=color)
        draw.rectangle([cx - half + 20, cy - half + 20, cx + half - 20, cy + half - 20], outline=light, width=4)
        for i in range(4):
            x = cx - half + 18 + i * (s - 36) // 3
            draw.line([x, cy + half - 16, x, cy + half], fill=dark, width=6)
    elif shape == "plate":
        pts = [(cx - half, cy + half // 2), (cx - half + 20, cy - half // 2), (cx + half - 20, cy - half // 2), (cx + half, cy + half // 2)]
        draw.polygon(pts, fill=color, outline=dark)
        draw.line([cx - half + 40, cy - 6, cx + half - 40, cy - 6], fill=light, width=4)
    elif shape == "hex":
        r = half
        pts = [
            (cx + r * math.cos(math.radians(60 * i - 30)), cy + r * math.sin(math.radians(60 * i - 30)))
            for i in range(6)
        ]
        draw.polygon(pts, fill=color, outline=dark)
        draw.ellipse([cx - r // 3, cy - r // 3, cx + r // 3, cy + r // 3], outline=light, width=4)
    elif shape == "gear":
        draw.ellipse([cx - half, cy - half, cx + half, cy + half], fill=color)
        for i in range(12):
            angle = math.radians(30 * i)
            tx = cx + int(half * 0.92 * math.cos(angle))
            ty = cy + int(half * 0.92 * math.sin(angle))
            draw.ellipse([tx - 12, ty - 12, tx + 12, ty + 12], fill=color, outline=dark)
        draw.ellipse([cx - half // 3, cy - half // 3, cx + half // 3, cy + half // 3], fill=(235, 235, 235))
    elif shape == "fan":
        draw.ellipse([cx - half, cy - half, cx + half, cy + half], outline=color, width=16)
        for i in range(5):
            angle = math.radians(72 * i)
            bx = cx + int(half * 0.5 * math.cos(angle))
            by = cy + int(half * 0.5 * math.sin(angle))
            draw.ellipse([bx - 26, by - 18, bx + 26, by + 18], fill=color)
        draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=dark)
    elif shape == "lamp":
        draw.rounded_rectangle([cx - half, cy - int(half * 0.5), cx + half, cy + int(half * 0.5)], radius=18, fill=(60, 60, 64))
        draw.rounded_rectangle([cx - half + 12, cy - int(half * 0.5) + 12, cx + half - 12, cy + int(half * 0.5) - 12], radius=10, fill=color)
        draw.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(255, 250, 210))
    elif shape == "seat":
        draw.rounded_rectangle([cx - half, cy - half, cx + half, cy], radius=16, fill=color)
        draw.rounded_rectangle([cx - half, cy + 4, cx + half, cy + half], radius=14, fill=tuple(max(0, c - 18) for c in color))
        draw.line([cx - half + 10, cy, cx + half - 10, cy], fill=dark, width=6)
    else:
        draw.ellipse([cx - half, cy - half, cx + half, cy + half], fill=color)


def render_part_image(
    shape: str,
    color: tuple[int, int, int],
    seed: int,
    part_number: str,
    size: int = 256,
) -> Image.Image:
    rng = random.Random(seed)
    img = _background(rng, size)
    draw = ImageDraw.Draw(img)
    color = _jitter(color, rng)
    _draw_shape(draw, shape, color, size, rng)

    for _ in range(rng.randint(40, 120)):
        x = rng.randint(0, size - 1)
        y = rng.randint(0, size - 1)
        v = rng.randint(-10, 10)
        px = img.getpixel((x, y))
        img.putpixel((x, y), tuple(max(0, min(255, c + v)) for c in px))

    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, size - 26, size, size], fill=(245, 245, 245))
    draw.text((8, size - 22), f"SYNTHETIC · {part_number}", fill=(90, 90, 90))
    return img


def save_part_image(
    output_dir: Path,
    category_slug: str,
    part_number: str,
    shape: str,
    color: tuple[int, int, int],
    seed: int,
    size: int = 256,
) -> Path:
    target_dir = output_dir / category_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{part_number}.png"
    render_part_image(shape, color, seed, part_number, size=size).save(path, format="PNG")
    return path
