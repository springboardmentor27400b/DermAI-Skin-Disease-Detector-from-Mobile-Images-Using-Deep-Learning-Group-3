"""Hair / thin-artifact removal (DullRazor-style) that leaves small round lesions alone.

Oriented line closings highlight dark thin structures; the candidate mask is then kept only where a connected component is
long and thin, so a small dark lesion (round, not elongated) is never painted over. Light-coloured hair is not handled.
"""
import cv2
import numpy as np

_ANGLES = range(0, 180, 15)


def _line_kernel(length: int, angle: int) -> np.ndarray:
    k = np.zeros((length, length), np.uint8)
    c = length // 2
    dx, dy = np.cos(np.deg2rad(angle)) * c, np.sin(np.deg2rad(angle)) * c
    cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
    return k


def hair_mask(rgb: np.ndarray, work: int = 384) -> tuple[np.ndarray, float]:
    """Returns (mask at input resolution, fraction of pixels flagged)."""
    H, W = rgb.shape[:2]
    s = min(1.0, work / max(H, W))
    small = cv2.resize(rgb, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgb
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), (0, 0), 1.0)   # sensor / JPEG noise must not read as hair
    L = max(9, int(0.045 * max(gray.shape)) | 1)
    bh = np.zeros_like(gray)
    for a in _ANGLES:
        bh = np.maximum(bh, cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, _line_kernel(L, a)))
    thr = max(12.0, float(np.median(bh)) + 6.0 * 1.4826 * float(np.median(np.abs(bh - np.median(bh)))))   # adapts to texture
    cand = (bh > thr).astype(np.uint8)
    # Thick blobs (a dark lesion or speck: wider than a hair) are cut out so they are never painted over or glue to hairs.
    r = max(2, int(0.2 * L))
    thick = cv2.morphologyEx(cand, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    cand = cand & (1 - cv2.dilate(thick, np.ones((5, 5), np.uint8)))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    keep = np.zeros_like(cand)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 0.6 * L and max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]) >= 0.8 * L:
            keep[lbl == i] = 1
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))
    frac = float(keep.mean())
    full = cv2.resize(keep, (W, H), interpolation=cv2.INTER_NEAREST) if s < 1 else keep
    return full, frac


def remove_hair(rgb: np.ndarray, work: int = 384) -> tuple[np.ndarray, float]:
    """Inpaint detected hairs. Returns (cleaned image, hair fraction). Unchanged image when almost no hair is found."""
    mask, frac = hair_mask(rgb, work)
    if frac < 0.002:
        return rgb, frac
    H, W = rgb.shape[:2]
    s = min(1.0, 768 / max(H, W))                       # inpaint at <=768 px to keep it fast, then blend back
    sm = cv2.resize(rgb, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgb
    mm = cv2.resize(mask, (sm.shape[1], sm.shape[0]), interpolation=cv2.INTER_NEAREST) if s < 1 else mask
    painted = cv2.inpaint(sm, (mm * 255).astype(np.uint8), 3, cv2.INPAINT_TELEA)
    if s < 1:
        up = cv2.resize(painted, (W, H), interpolation=cv2.INTER_CUBIC)
        out = rgb.copy(); out[mask > 0] = up[mask > 0]
        return out, frac
    return painted, frac

