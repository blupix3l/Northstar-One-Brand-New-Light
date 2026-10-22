"""
Color Extraction for Adaptive Toolbar Tinting
=============================================
Extracts a representative accent color from a webpage snapshot
using k-means clustering on downscaled pixel data.
"""

import math
from typing import Optional, List, Tuple

from PyQt6.QtGui import QPixmap, QColor, QImage
from PyQt6.QtCore import Qt


def extract_accent_color(pixmap: QPixmap) -> Optional[QColor]:
    """
    Extract a dominant accent color from a QPixmap.

    Downsamples to 64x64, filters near-white/near-black/transparent pixels,
    then runs k-means clustering to find the dominant non-neutral color.

    Returns None if fewer than 50 valid pixels exist (fallback signal).
    """
    if pixmap.isNull():
        return None

    small = pixmap.scaled(64, 64, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.FastTransformation)
    img = small.toImage().convertToFormat(QImage.Format.Format_ARGB32)

    pixels: List[Tuple[int, int, int]] = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            if a < 10:
                continue
            if r > 240 and g > 240 and b > 240:
                continue
            if r < 15 and g < 15 and b < 15:
                continue
            pixels.append((r, g, b))

    if len(pixels) < 50:
        return None

    centroids = _kmeans(pixels, k=5, iterations=10)

    best_cluster = None
    best_count = 0
    for cx, cy, cz, members in centroids:
        if cx > 235 and cy > 235 and cz > 235:
            continue
        if cx < 20 and cy < 20 and cz < 20:
            continue
        if members > best_count:
            best_count = members
            best_cluster = (cx, cy, cz)

    if best_cluster is None:
        return None

    return QColor(min(255, max(0, int(best_cluster[0]))),
                  min(255, max(0, int(best_cluster[1]))),
                  min(255, max(0, int(best_cluster[2]))))


def _kmeans(pixels: List[Tuple[int, int, int]], k: int = 5,
            iterations: int = 10) -> List[Tuple[float, float, float, int]]:
    """
    Simple k-means on RGB pixels.

    Returns list of (r, g, b, member_count) tuples for each centroid.
    """
    n = len(pixels)
    step = max(1, n // k)
    centroids = [(float(pixels[i][0]), float(pixels[i][1]), float(pixels[i][2]), 0)
                 for i in range(0, min(n, k * step), step)][:k]

    if not centroids:
        return []

    labels = [0] * n

    for _ in range(iterations):
        for idx, (pr, pg, pb) in enumerate(pixels):
            best = 0
            best_d = float("inf")
            for ci, (cr, cg, cb, _) in enumerate(centroids):
                d = (pr - cr) ** 2 + (pg - cg) ** 2 + (pb - cb) ** 2
                if d < best_d:
                    best_d = d
                    best = ci
            labels[idx] = best

        sums = [[0.0, 0.0, 0.0, 0] for _ in range(k)]
        for idx, (pr, pg, pb) in enumerate(pixels):
            c = labels[idx]
            sums[c][0] += pr
            sums[c][1] += pg
            sums[c][2] += pb
            sums[c][3] += 1

        for ci in range(k):
            count = sums[ci][3]
            if count > 0:
                centroids[ci] = (sums[ci][0] / count, sums[ci][1] / count,
                                 sums[ci][2] / count, count)
            else:
                centroids[ci] = (centroids[ci][0], centroids[ci][1],
                                 centroids[ci][2], 0)

    return centroids


def reconstruct_tint(hue: float, dark: bool, opacity: float = 0.88) -> str:
    """
    Reconstruct a subtle tint string from a hue value.

    Dark theme:  H=hue, S=20%, L=12%
    Light theme: H=hue, S=15%, L=92%

    Returns an rgba() CSS color string.
    """
    if dark:
        s = min(20, 20) / 100.0
        l = 12 / 100.0
    else:
        s = min(15, 15) / 100.0
        l = 92 / 100.0

    r, g, b = _hsl_to_rgb(hue / 360.0, s, l)
    r = int(min(255, max(0, r * 255)))
    g = int(min(255, max(0, g * 255)))
    b = int(min(255, max(0, b * 255)))

    return f"rgba({r},{g},{b},{opacity})"


def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[float, float, float]:
    """Convert HSL (h in 0-1 range) to RGB (0-1 range)."""
    if s == 0:
        return (l, l, l)

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1.0
        if t > 1:
            t -= 1.0
        if t < 1 / 6:
            return p + (q - p) * 6.0 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2.0 / 3.0 - t) * 6.0
        return p

    q = l * (1.0 + s) if l < 0.5 else l + s - l * s
    p = 2.0 * l - q
    return (hue_to_rgb(p, q, h + 1 / 3),
            hue_to_rgb(p, q, h),
            hue_to_rgb(p, q, h - 1 / 3))
