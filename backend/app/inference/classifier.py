"""Loads the active TorchScript classifier and turns a preprocessed ROI image into a calibrated prediction.

Model folder:  <model_dir>/<version>/model.ts.pt + meta.json     (written by ml/export_model.py)
Active model:  settings.active_model, else <model_dir>/active.json {"version": "..."}.
torch is imported lazily: without it (or without a model) the API still works and images stay 'pending'.
"""
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.preprocessing.pipeline import model_input

DISCLAIMER = "AI-assisted analysis for screening and research. It is not a medical diagnosis. Please have any skin concern assessed by a qualified clinician."
_lock = threading.Lock()
_cache: dict = {}


@dataclass
class Loaded:
    version: str
    meta: dict
    module: object


def _active_version() -> str | None:
    if settings.active_model:
        return settings.active_model
    f = Path(settings.model_dir) / "active.json"
    if f.is_file():
        try:
            return json.loads(f.read_text()).get("version")
        except (ValueError, OSError):
            return None
    return None


def active_version() -> str | None:
    return _active_version()


def list_versions() -> list[str]:
    d = Path(settings.model_dir)
    return sorted(p.name for p in d.iterdir() if (p / "meta.json").is_file()) if d.is_dir() else []


def reload() -> None:
    with _lock:
        _cache.clear()


def get_model() -> Loaded | None:
    version = _active_version()
    if not version:
        return None
    with _lock:
        if _cache.get("version") == version:
            return _cache.get("loaded")
        loaded = None
        folder = Path(settings.model_dir) / version
        try:
            import torch
            torch.set_num_threads(settings.inference_threads)
            meta = json.loads((folder / "meta.json").read_text())
            module = torch.jit.load(str(folder / "model.ts.pt"), map_location="cpu").eval()
            loaded = Loaded(version, meta, module)
        except Exception:                      # missing torch, missing files, corrupt model -> run without a classifier
            loaded = None
        _cache.update(version=version, loaded=loaded)
        return loaded


def preprocessing_flags() -> dict:
    """The preprocessing recipe the active model was trained with (meta.json "preprocessing", written by precompute_rois.py).
    Keys missing from older models default to today's pipeline."""
    m = get_model()
    text = (m.meta.get("preprocessing") if m else None) or ""
    kv = dict(p.split("=", 1) for p in text.split() if "=" in p)
    on = lambda k: kv.get(k, "true").lower() != "false"
    try:
        size = int(kv.get("size", settings.roi_size))
    except ValueError:
        size = settings.roi_size
    try:
        roi_min = float(kv.get("roi_min", 0.3))
    except ValueError:
        roi_min = 0.3
    return {"size": size, "enhance": on("enhance"), "lesion_roi": on("lesion_roi"), "hair_removal": on("hair_removal"), "roi_min": roi_min}


def is_available() -> bool:
    return get_model() is not None


def predict(preview_rgb: np.ndarray, caveats: list[str] | None = None, top_n: int = 3) -> dict:
    m = get_model()
    if m is None:
        raise RuntimeError("No classifier is deployed.")
    import torch
    meta = m.meta
    x = model_input(preview_rgb, meta["img_size"], meta["mean"], meta["std"])
    with torch.no_grad():
        logits = m.module(torch.from_numpy(x)[None]).float()[0] / float(meta.get("temperature", 1.0))
        p = torch.softmax(logits, 0).numpy()
    classes, names = meta["classes"], meta.get("class_names", {})
    order = np.argsort(-p)
    top = [{"label": classes[i], "name": names.get(classes[i], classes[i]), "probability": round(float(p[i]), 4)} for i in order[:top_n]]
    conf = float(p[order[0]])
    return {
        "label": top[0]["label"], "label_name": top[0]["name"], "confidence": round(conf, 4), "top_n": top,
        "probabilities": {classes[i]: round(float(p[i]), 4) for i in range(len(classes))},
        "low_confidence": conf < settings.low_confidence_threshold,
        "caveats": caveats or [],
        "model": {"version": m.version, "arch": meta.get("arch"), "temperature": meta.get("temperature", 1.0)},
        "analysed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
    }


def describe(include_evaluation: bool) -> dict:
    m = get_model()
    if m is None:
        return {"available": False, "versions": list_versions(), "active": _active_version()}
    out = {"available": True, "version": m.version, "arch": m.meta.get("arch"), "classes": m.meta["classes"],
           "class_names": m.meta.get("class_names", {}), "dataset": m.meta.get("dataset"), "trained_at": m.meta.get("created_at"), "preprocessing": m.meta.get("preprocessing"),
           "members": m.meta.get("members"), "explain": m.meta.get("explain"), "versions": list_versions()}
    if include_evaluation:
        out["evaluation"] = m.meta.get("evaluation")
    return out

