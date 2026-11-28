"""Skin-region detection: an adaptive colour model, so it works across skin tones better than fixed RGB/HSV ranges.

Stage 1 takes pixels inside a permissive skin-hue prior (YCrCb), stage 2 fits a Gaussian to their Lab a/b chroma and keeps
pixels within a few standard deviations. A lesion itself may fall outside the model; callers treat this as 'skin around it'.
"""
import cv2
import numpy as np


def skin_mask(rgb: np.ndarray, work: int = 256) -> tuple[np.ndarray, float]:
    H, W = rgb.shape[:2]
    s = min(1.0, work / max(H, W))
    sm = cv2.resize(rgb, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgb
    ycc = cv2.cvtColor(sm, cv2.COLOR_RGB2YCrCb)
    prior = (ycc[..., 1] >= 128) & (ycc[..., 1] <= 185) & (ycc[..., 2] >= 70) & (ycc[..., 2] <= 140) & (ycc[..., 0] >= 40)
    if prior.sum() < 0.02 * prior.size:
        return np.zeros((H, W), np.uint8), 0.0
    lab = cv2.cvtColor(sm, cv2.COLOR_RGB2LAB).astype(np.float32)
    ab = lab[..., 1:][prior]
    mu = np.median(ab, 0)
    cov = np.cov(ab.T) + np.eye(2) * 1.0
    diff = lab[..., 1:] - mu
    maha = np.einsum("...i,ij,...j->...", diff, np.linalg.inv(cov), diff)
    m = (maha < 9.0).astype(np.uint8)                       # about 3 sigma
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    frac = float(m.mean())
    return (cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST) if s < 1 else m), frac


def border_bars(rgb: np.ndarray, std_max: float = 3.0, min_frac: float = 0.08) -> bool:
    """True when a side of the image is a blank band (letterboxing, screenshot edges): a sign of an incomplete / padded photo."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = g.shape
    def run(vals):
        n = 0
        for v in vals:
            if v < std_max: n += 1
            else: break
        return n
    rows, cols = g.std(1), g.std(0)
    return any(run(v) / len(v) >= min_frac for v in (rows, rows[::-1], cols, cols[::-1]))

