"""Heuristic image quality assessment (blur, brightness, contrast).

Thresholds are provisional (see docs/quality_thresholds.md) and are validated against labelled
good/poor photos in Milestone 2.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.preprocessing.hair import hair_mask
from app.preprocessing.skin import border_bars, skin_mask

from app.core.config import settings

# --- thresholds: set in app/core/config.py, override with QUALITY_* environment variables -------------
BLUR_POOR = settings.quality_blur_poor
BLUR_ACCEPTABLE = settings.quality_blur_acceptable
DARK_POOR = settings.quality_dark_poor
DARK_ACCEPTABLE = settings.quality_dark_acceptable
BRIGHT_POOR = settings.quality_bright_poor
BRIGHT_ACCEPTABLE = settings.quality_bright_acceptable
CONTRAST_POOR = settings.quality_contrast_poor
CONTRAST_ACCEPTABLE = settings.quality_contrast_acceptable
_ANALYSIS_MAX_SIDE = 512


@dataclass
class QualityReport:
    label: str                     # good | acceptable | poor
    blur_score: float
    brightness: float
    contrast: float
    issues: list[str] = field(default_factory=list)
    skin_fraction: float = 0.0
    hair_fraction: float = 0.0
    occlusion_fraction: float = 0.0

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "blur_score": round(self.blur_score, 2),
            "brightness": round(self.brightness, 2),
            "contrast": round(self.contrast, 2),
            "issues": self.issues,
            "skin_fraction": round(self.skin_fraction, 3), "hair_fraction": round(self.hair_fraction, 3),
            "occlusion_fraction": round(self.occlusion_fraction, 3),
        }


def assess_quality(rgb: np.ndarray) -> QualityReport:
    """rgb: HxWx3 uint8."""
    h, w = rgb.shape[:2]
    scale = _ANALYSIS_MAX_SIDE / max(h, w)
    if scale < 1:
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())

    severity = 0  # 0 good, 1 acceptable, 2 poor
    issues: list[str] = []

    def flag(level: int, msg: str) -> None:
        nonlocal severity
        severity = max(severity, level)
        issues.append(msg)

    if blur < BLUR_POOR:
        flag(2, "Image is blurred. Hold the camera steady and tap to focus.")
    elif blur < BLUR_ACCEPTABLE:
        flag(1, "Image is slightly soft.")

    if brightness < DARK_POOR:
        flag(2, "Image is too dark. Move to better lighting.")
    elif brightness < DARK_ACCEPTABLE:
        flag(1, "Lighting is dim.")
    elif brightness > BRIGHT_POOR:
        flag(2, "Image is overexposed. Avoid direct flash or glare.")
    elif brightness > BRIGHT_ACCEPTABLE:
        flag(1, "Image is bright; highlights may be clipped.")

    if contrast < CONTRAST_POOR:
        flag(2, "Very low contrast; the lesion may not be visible.")
    elif contrast < CONTRAST_ACCEPTABLE:
        flag(1, "Low contrast.")

    # Informational checks: they can lower "good" to "acceptable" but never make a photo "poor" on their own.
    skin, skin_frac = skin_mask(rgb)
    _, hair_frac = hair_mask(rgb)
    occl = _occlusion_fraction(skin)
    if border_bars(rgb):
        flag(1, "The photo has blank borders. Make sure the whole photo was captured.")
    if skin_frac < settings.quality_skin_fraction_low:
        flag(1, "Much of the photo is not skin. Move closer so the skin fills the frame.")
    if occl >= settings.quality_occlusion_fraction:
        flag(1, "Something (clothing, a finger or an object) may be covering part of the skin.")
    if hair_frac > settings.quality_hair_fraction_high:
        flag(1, "Hair covers part of the skin; it is removed digitally but may hide detail.")

    label = ("good", "acceptable", "poor")[severity]
    return QualityReport(label, blur, brightness, contrast, issues, skin_frac, hair_frac, occl)


def _occlusion_fraction(skin: np.ndarray) -> float:
    """Largest non-skin region that touches the frame edge and stays clear of the centre (where the lesion is)."""
    h, w = skin.shape
    non = (1 - skin).astype(np.uint8)
    non[int(h * .3):int(h * .7), int(w * .3):int(w * .7)] = 0
    non = cv2.morphologyEx(non, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(non, connectivity=8)
    best = 0.0
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if (x == 0 or y == 0 or x + bw >= w or y + bh >= h) and a / (h * w) > best:
            best = a / (h * w)
    return float(best)

