"""Explainable AI: Grad-CAM / Grad-CAM++ attention maps for the deployed classifier.

The classifier itself is a TorchScript file, which cannot be hooked. ml/export_model.py therefore also writes the network split in two
TorchScript modules next to it: features.ts.pt (image -> feature map B,C,H,W) and head.ts.pt (feature map -> class logits). Grad-CAM then
needs only autograd between those two. An ensemble ships one pair per member (subfolders listed in meta.json "explain": {"members": [...]})
and the maps are averaged. Without these files (or without torch) the API simply returns no attention map.

An attention map shows where the model looked. It is not evidence that the prediction is clinically right.
"""
import threading
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.inference import classifier
from app.preprocessing.lesion import LesionResult, roi_square
from app.preprocessing.pipeline import center_square_crop, model_input

_lock = threading.Lock()
_cache: dict = {}


def _load():
    m = classifier.get_model()
    if m is None:
        return None
    with _lock:
        if _cache.get("loaded") is m:
            return _cache.get("pairs")
        pairs = None
        try:
            import torch
            spec = m.meta.get("explain") or {}
            folder = Path(settings.model_dir) / m.version
            pairs = []
            for sub in spec.get("members") or [""]:
                d = folder / sub if sub else folder
                pairs.append((torch.jit.load(str(d / "features.ts.pt"), map_location="cpu").eval(),
                              torch.jit.load(str(d / "head.ts.pt"), map_location="cpu").eval()))
        except Exception:               # missing files / torch -> no explanations, classification keeps working
            pairs = None
        _cache.update(loaded=m, pairs=pairs)
        return pairs


def available() -> bool:
    return _load() is not None


def heatmap(preview_rgb: np.ndarray, class_idx: int, method: str | None = None) -> np.ndarray | None:
    """Attention map for class_idx on the model's input grid (img_size x img_size), floats in 0..1. None when unavailable."""
    pairs = _load()
    m = classifier.get_model()
    if not pairs or m is None:
        return None
    import torch
    import torch.nn.functional as F
    method = method or settings.explain_method
    size = m.meta["img_size"]
    x = torch.from_numpy(model_input(preview_rgb, size, m.meta["mean"], m.meta["std"]))[None]
    cams = []
    with torch.enable_grad():
        for feats, head in pairs:
            with torch.no_grad():
                a = feats(x)
            a = a.detach().requires_grad_(True)
            g = torch.autograd.grad(head(a)[0, class_idx], a)[0]
            if method == "gradcampp":
                g2 = g ** 2
                denom = 2 * g2 + a.sum((2, 3), keepdim=True) * g2 * g
                alpha = g2 / torch.where(denom != 0, denom, torch.ones_like(denom))
                w = (alpha * F.relu(g)).sum((2, 3), keepdim=True)
            else:
                w = g.mean((2, 3), keepdim=True)
            cam = F.relu((w * a).sum(1, keepdim=True))
            cam = F.interpolate(cam, size=(size, size), mode="bilinear", align_corners=False)[0, 0].detach()
            mx = float(cam.max())
            cams.append(cam / mx if mx > 1e-8 else torch.zeros_like(cam))
    heat = torch.stack(cams).mean(0).detach().numpy()
    mx = float(heat.max())
    return (heat / mx if mx > 1e-8 else heat).astype(np.float32)


def saliency(preview_rgb: np.ndarray, class_idx: int) -> np.ndarray | None:
    """Vanilla gradient saliency: how much each input pixel changes the score of class_idx (max over colour channels, smoothed).
    Works on the full TorchScript model, so it needs no features/head split. Floats in 0..1, on the model's input grid. None if no model."""
    m = classifier.get_model()
    if m is None:
        return None
    import torch
    size = m.meta["img_size"]
    x = torch.from_numpy(model_input(preview_rgb, size, m.meta["mean"], m.meta["std"]))[None].clone().requires_grad_(True)
    with torch.enable_grad():
        score = m.module(x)[0, class_idx]
        g = torch.autograd.grad(score, x)[0]
    s = g.abs().amax(1)[0].detach().numpy().astype(np.float32)
    s = cv2.GaussianBlur(s, (0, 0), max(1.0, size / 112))
    hi = float(np.percentile(s, 99.5))
    return np.clip(s / hi, 0, 1).astype(np.float32) if hi > 1e-12 else np.zeros_like(s)


def saliency_overlay(preview_rgb: np.ndarray, sal: np.ndarray, alpha: float = 0.6) -> np.ndarray:
    """Saliency blended over the preprocessed image with a different colour map from Grad-CAM, so the two are not confused."""
    h, w = preview_rgb.shape[:2]
    sm = np.clip(cv2.resize(sal, (w, h), interpolation=cv2.INTER_CUBIC), 0, 1)
    colour = cv2.cvtColor(cv2.applyColorMap((sm * 255).astype(np.uint8), cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB).astype(np.float32)
    a = (alpha * np.clip(sm * 1.5, 0, 1))[..., None]
    return np.clip(preview_rgb.astype(np.float32) * (1 - a) + colour * a, 0, 255).astype(np.uint8)


def stability(preview_rgb: np.ndarray, class_idx: int, heat: np.ndarray, method: str | None = None) -> float | None:
    """Explanation stability: correlation (-1..1) between the attention map and the attention map of the horizontally flipped photo,
    flipped back. A model that looks at the same place whichever way the photo is mirrored scores near 1. None if undefined."""
    flipped = heatmap(np.ascontiguousarray(preview_rgb[:, ::-1]), class_idx, method)
    if flipped is None:
        return None
    a, b = heat.ravel().astype(np.float64), flipped[:, ::-1].ravel().astype(np.float64)
    if a.std() < 1e-8 or b.std() < 1e-8:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def overlay(preview_rgb: np.ndarray, heat: np.ndarray, alpha: float | None = None) -> np.ndarray:
    """Heat-map blended over the preprocessed image; cold areas stay transparent so the lesion remains visible."""
    alpha = settings.explain_overlay_alpha if alpha is None else alpha
    h, w = preview_rgb.shape[:2]
    hm = np.clip(cv2.resize(heat, (w, h), interpolation=cv2.INTER_CUBIC), 0, 1)
    colour = cv2.cvtColor(cv2.applyColorMap((hm * 255).astype(np.uint8), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB).astype(np.float32)
    a = (alpha * np.clip(hm * 1.5, 0, 1))[..., None]
    return np.clip(preview_rgb.astype(np.float32) * (1 - a) + colour * a, 0, 255).astype(np.uint8)


def lesion_overlap(heat: np.ndarray, lesion: LesionResult, image_shape: tuple[int, int], use_roi: bool, roi_min_frac: float = 0.3) -> dict | None:
    """Share of the attention that falls inside the detected lesion, next to how much of the crop the lesion covers.
    (Attention far above the lesion's share means the model focused on it; roughly equal means it did not especially.)"""
    if not lesion.found or lesion.mask is None:
        return None
    if use_roi:
        x, y, side = roi_square(lesion, image_shape, min_frac=roi_min_frac)
        mask = lesion.mask[y:y + side, x:x + side]
    else:
        mask = center_square_crop(lesion.mask)
    mask = cv2.resize(mask, (heat.shape[1], heat.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    total = float(heat.sum())
    if total <= 0 or not mask.any():
        return None
    return {"attention_in_lesion": round(float(heat[mask].sum()) / total, 3), "lesion_share_of_crop": round(float(mask.mean()), 3)}

