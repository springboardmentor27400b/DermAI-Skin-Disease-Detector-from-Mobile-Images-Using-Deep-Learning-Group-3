"""Classical lesion detection / segmentation (no training data needed).

PAD-UFES-20 ships no lesion masks, so M2 uses a transparent colour-model approach:
  1. fit a plane to the Lab colour of the image border (the skin background, robust to lighting gradients),
  2. measure each pixel's colour distance from that skin model,
  3. Otsu threshold (never below a noise floor) -> clean up -> keep the component nearest the centre,
  4. optionally refine the boundary with GrabCut.
Extra components of significant size are reported as additional lesions.

A U-Net can replace this once masks exist (Milestone 3). Judge results by eye with ml/segment_review.py.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

try:                                   # the optional trained segmenter; ml/ scripts run without the API's dependencies
    from app.inference import segmenter
except ImportError:
    segmenter = None
from app.preprocessing.hair import remove_hair

_MAX_SIDE = 384
_MIN_AREA_FRAC = 0.004
_MAX_AREA_FRAC = 0.85


@dataclass
class LesionResult:
    found: bool
    mask: np.ndarray | None = None          # HxW uint8 {0,1} at the ORIGINAL resolution (main lesion only)
    bbox: tuple[int, int, int, int] | None = None   # x0, y0, x1, y1 in original pixels
    area_fraction: float = 0.0
    contrast_ratio: float = 0.0             # mean colour distance inside / noise level of the skin
    solidity: float = 0.0
    lesion_count: int = 0
    other_boxes: list[tuple[int, int, int, int]] = field(default_factory=list)
    method: str = "none"
    hair_fraction: float = 0.0

    def info(self) -> dict:
        return {
            "found": self.found, "bbox": list(self.bbox) if self.bbox else None,
            "area_fraction": round(self.area_fraction, 4), "contrast_ratio": round(self.contrast_ratio, 2),
            "solidity": round(self.solidity, 3), "lesion_count": self.lesion_count,
            "other_boxes": [list(b) for b in self.other_boxes], "method": self.method, "hair_fraction": round(self.hair_fraction, 4),
        }


def _fit_plane(lab: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Per-channel plane a + b*x + c*y fitted on ring pixels with one outlier-rejection pass."""
    h, w = lab.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    X = np.stack([np.ones(h * w), (xx / w).ravel(), (yy / h).ravel()], 1)
    idx = np.flatnonzero(ring.ravel())
    out = np.empty((h * w, 3), np.float32)
    for c in range(3):
        y = lab[..., c].ravel()
        keep = idx
        for _ in range(2):
            coef, *_ = np.linalg.lstsq(X[keep], y[keep], rcond=None)
            res = np.abs(y[idx] - X[idx] @ coef)
            mad = 1.4826 * np.median(res) + 1e-6
            keep = idx[res < 2.5 * mad]
            if len(keep) < 50:
                keep = idx
        out[:, c] = X @ coef
    return out.reshape(h, w, 3)


def _fill_holes(m: np.ndarray) -> np.ndarray:
    flood = m.copy()
    h, w = m.shape
    cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    return m | (1 - flood)


def detect_lesion(rgb: np.ndarray, refine: bool = True) -> LesionResult:
    H, W = rgb.shape[:2]
    s = min(1.0, _MAX_SIDE / max(H, W))
    small = cv2.resize(rgb, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgb
    small, hair = remove_hair(small, work=max(small.shape[:2]))     # hairs would otherwise read as lesion edges
    res = _detect(small, H, W, refine)
    res.hair_fraction = hair
    return res


def _detect(small: np.ndarray, H: int, W: int, refine: bool) -> LesionResult:
    s = small.shape[1] / W
    h, w = small.shape[:2]
    sigma = max(1.0, 0.004 * max(h, w))
    lab = cv2.cvtColor(cv2.GaussianBlur(small, (0, 0), sigma), cv2.COLOR_RGB2LAB).astype(np.float32)

    ring = np.ones((h, w), bool)
    ring[int(h * .14):int(h * .86), int(w * .14):int(w * .86)] = False
    bg = _fit_plane(lab, ring)
    d = np.sqrt((0.5 * (lab[..., 0] - bg[..., 0])) ** 2 + (lab[..., 1] - bg[..., 1]) ** 2 + (lab[..., 2] - bg[..., 2]) ** 2)
    noise = float(1.4826 * np.median(d[ring]) + 1e-3)

    d8 = np.clip(d / max(np.percentile(d, 99.5), 1e-3) * 255, 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    t = max(otsu / 255 * max(np.percentile(d, 99.5), 1e-3), 3.5 * noise + 2.0)
    m = (d > t).astype(np.uint8)
    seg = segmenter.predict(small) if segmenter is not None else None
    if seg is not None:                      # a trained model replaces the colour model's mask
        m = (seg > 0.5).astype(np.uint8)
        refine = False
    k = max(3, int(0.02 * max(h, w)) | 1)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    m = _fill_holes(m)

    n, lbl, stats, cent = cv2.connectedComponentsWithStats(m, connectivity=8)
    diag = float(np.hypot(h, w))
    cands = []
    for i in range(1, n):
        frac = stats[i, cv2.CC_STAT_AREA] / (h * w)
        if frac < _MIN_AREA_FRAC:
            continue
        dist = np.hypot(cent[i][0] - w / 2, cent[i][1] - h / 2) / diag
        cands.append((frac * np.exp(-(dist / 0.25) ** 2), i, frac))
    if not cands:
        return LesionResult(False, method="no_component")
    cands.sort(reverse=True)
    best_score, bi, frac = cands[0]
    if frac > _MAX_AREA_FRAC:
        return LesionResult(False, method="region_too_large")
    main = (lbl == bi).astype(np.uint8)
    method = "colour_model" if seg is None else "segmentation_model"

    if refine:
        try:
            core = cv2.erode(main, np.ones((k, k), np.uint8))
            if core.sum() > 20:
                gc = np.full((h, w), cv2.GC_BGD, np.uint8)
                gc[cv2.dilate(main, np.ones((3 * k, 3 * k), np.uint8)) > 0] = cv2.GC_PR_BGD
                gc[main > 0] = cv2.GC_PR_FGD
                gc[core > 0] = cv2.GC_FGD
                cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
                g = _fill_holes(((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8))
                nn, l2, st2, _ = cv2.connectedComponentsWithStats(g, connectivity=8)
                if nn > 1:
                    g = (l2 == 1 + int(np.argmax(st2[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
                    if 0.5 < g.sum() / main.sum() < 2.0:
                        main, method = g, "colour_model+grabcut"
        except cv2.error:
            pass

    frac = float(main.sum()) / (h * w)
    if frac < _MIN_AREA_FRAC or frac > _MAX_AREA_FRAC:
        return LesionResult(False, method="refined_region_invalid")
    cnts, _ = cv2.findContours(main, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    hull = cv2.contourArea(cv2.convexHull(c))
    solidity = float(cv2.contourArea(c) / hull) if hull > 0 else 0.0
    x, y, bw, bh = cv2.boundingRect(c)
    # Plausibility gate for the colour model only (tuned by eye on PAD-UFES-20): a region that hugs the frame edge, sits far from the
    # centre, or is a thin strip is far more likely a shadow, crease or hair. A trained segmenter is trusted, so it skips this gate
    # (a large lesion filling the frame is legitimate).
    if seg is None:
        m = 0.02 * max(h, w)
        (_, _), (rw, rh), _ = cv2.minAreaRect(c)
        aspect = max(rw, rh) / max(min(rw, rh), 1.0)
        cx, cy = x + bw / 2, y + bh / 2
        if x <= m or y <= m or x + bw >= w - m or y + bh >= h - m:
            return LesionResult(False, method="rejected_touches_edge")
        if np.hypot(cx - w / 2, cy - h / 2) > 0.28 * min(h, w):
            return LesionResult(False, method="rejected_off_centre")
        if aspect > 3.0 or solidity < 0.6:
            return LesionResult(False, method="rejected_shape")
    sx, sy = W / w, H / h
    bbox = (int(x * sx), int(y * sy), int((x + bw) * sx), int((y + bh) * sy))
    others = []
    main_frac0 = frac
    for sc, i, f in cands[1:]:
        if i != bi and f >= 0.2 * main_frac0:           # judged by size: a second spot need not be central
            ox, oy, ow, oh = (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT])
            others.append((int(ox * sx), int(oy * sy), int((ox + ow) * sx), int((oy + oh) * sy)))
    full = cv2.resize(main, (W, H), interpolation=cv2.INTER_NEAREST) if s < 1 else main
    return LesionResult(True, full, bbox, frac, float(d[main > 0].mean() / noise), solidity, 1 + len(others), others, method)


def roi_square(lesion: LesionResult, shape: tuple[int, int], pad: float = 0.25, min_frac: float = 0.3) -> tuple[int, int, int]:
    """Square crop (x0, y0, side) around the lesion with context. Falls back to the centre square."""
    H, W = shape
    if not lesion.found or lesion.bbox is None:
        side = min(H, W)
        return (W - side) // 2, (H - side) // 2, side
    x0, y0, x1, y1 = lesion.bbox
    side = int(max(x1 - x0, y1 - y0) * (1 + 2 * pad))
    side = max(side, int(min_frac * min(H, W)))
    side = min(side, H, W)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    x = int(np.clip(cx - side // 2, 0, W - side))
    y = int(np.clip(cy - side // 2, 0, H - side))
    return x, y, side


def overlay(rgb: np.ndarray, lesion: LesionResult, max_side: int = 512, roi_min_frac: float = 0.3) -> np.ndarray:
    """Original image with the lesion outline, ROI square and other detections drawn on it."""
    H, W = rgb.shape[:2]
    s = min(1.0, max_side / max(H, W))
    img = cv2.resize(rgb, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA).copy() if s < 1 else rgb.copy()
    if lesion.found and lesion.mask is not None:
        m = cv2.resize(lesion.mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        tint = img.copy(); tint[m > 0] = (0.65 * tint[m > 0] + 0.35 * np.array([30, 200, 120])).astype(np.uint8)
        img = tint
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cnts, -1, (20, 230, 120), 2)
        x, y, side = roi_square(lesion, (H, W), min_frac=roi_min_frac)
        cv2.rectangle(img, (int(x * s), int(y * s)), (int((x + side) * s), int((y + side) * s)), (255, 255, 255), 1)
        for bx0, by0, bx1, by1 in lesion.other_boxes:
            cv2.rectangle(img, (int(bx0 * s), int(by0 * s)), (int(bx1 * s), int(by1 * s)), (255, 190, 0), 2)
    return img

