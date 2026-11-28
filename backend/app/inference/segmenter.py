"""Optional trained lesion segmenter (ml/train_seg.py). Files: <model_dir>/segmentation.ts.pt + segmentation.json.
Absent or without torch -> the colour-model detector is used."""
import json
import threading
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings

_lock = threading.Lock()
_state: dict = {}


def reload() -> None:
    with _lock:
        _state.clear()


def _load():
    with _lock:
        if "m" in _state:
            return _state["m"]
        m = None
        d = Path(settings.model_dir)
        try:
            import torch
            meta = json.loads((d / "segmentation.json").read_text())
            m = (torch.jit.load(str(d / "segmentation.ts.pt"), map_location="cpu").eval(), meta)
        except Exception:
            m = None
        _state["m"] = m
        return m


def info() -> dict | None:
    m = _load()
    return {"arch": m[1].get("arch"), "evaluation": m[1].get("evaluation")} if m else None


def predict(rgb: np.ndarray) -> np.ndarray | None:
    """Probability map (HxW float32 in 0..1) at the input resolution, or None when no segmenter is deployed."""
    m = _load()
    if m is None:
        return None
    import torch
    net, meta = m
    s = meta["img_size"]
    x = (cv2.resize(rgb, (s, s), interpolation=cv2.INTER_AREA).astype(np.float32) / 255 - np.array(meta["mean"], np.float32)) / np.array(meta["std"], np.float32)
    with torch.no_grad():
        p = torch.sigmoid(net(torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1)))[None]))[0, 0].numpy()
    return cv2.resize(p, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)

