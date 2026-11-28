"""Segmentation metrics from the brief: Dice, IoU, pixel accuracy, sensitivity, specificity, Hausdorff distance."""
import cv2
import numpy as np


def _boundary(m: np.ndarray) -> np.ndarray:
    m = m.astype(np.uint8)
    return m - cv2.erode(m, np.ones((3, 3), np.uint8))


def hausdorff(a: np.ndarray, b: np.ndarray) -> float:
    """Symmetric Hausdorff distance in pixels between mask boundaries (inf if either mask is empty)."""
    if not a.any() or not b.any():
        return float("inf")
    ba, bb = _boundary(a), _boundary(b)
    if not ba.any(): ba = a.astype(np.uint8)          # a mask that fills the whole frame has no inner boundary
    if not bb.any(): bb = b.astype(np.uint8)
    dt_b = cv2.distanceTransform((1 - bb).astype(np.uint8), cv2.DIST_L2, 3)
    dt_a = cv2.distanceTransform((1 - ba).astype(np.uint8), cv2.DIST_L2, 3)
    return float(max(dt_b[ba > 0].max(), dt_a[bb > 0].max()))


def seg_scores(pred: np.ndarray, gt: np.ndarray) -> dict:
    p, g = pred.astype(bool), gt.astype(bool)
    tp, fp, fn = (p & g).sum(), (p & ~g).sum(), (~p & g).sum()
    tn = (~p & ~g).sum()
    return {"dice": float(2 * tp / max(2 * tp + fp + fn, 1)), "iou": float(tp / max(tp + fp + fn, 1)),
            "pixel_accuracy": float((tp + tn) / p.size), "sensitivity": float(tp / max(tp + fn, 1)),
            "specificity": float(tn / max(tn + fp, 1)), "hausdorff_px": hausdorff(p, g)}


def mean_scores(rows: list[dict]) -> dict:
    out = {}
    for k in (k for k in rows[0] if not isinstance(rows[0][k], str)):      # skip the image-name column
        v = np.array([r[k] for r in rows], dtype=float)
        out[k] = float(np.mean(v[np.isfinite(v)])) if np.isfinite(v).any() else float("inf")
    out["n"] = len(rows)
    return out

