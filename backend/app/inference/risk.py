"""Risk categories (brief section 8). Low / Moderate / High / Requires Clinical Review.

The brief forbids inventing clinical thresholds, so none are hard-coded here. They come from <model_dir>/<version>/risk.json, written by
ml/risk_protocol.py from the model's own out-of-fold validation predictions (see docs/risk_protocol.md). The only dataset-defined input
is which classes are skin cancers: in PAD-UFES-20 every BCC, SCC and melanoma is biopsy-confirmed.

  p_malignant = sum of the model's probabilities for the malignant classes
  Low       p_malignant <  t_low    (t_low chosen so that >= target_sensitivity of malignant validation images are at or above it)
  High      p_malignant >= t_high   (t_high chosen so that >= high_specificity of non-malignant validation images are below it)
  Moderate  in between
  Requires Clinical Review replaces Low when the lesion could not be located, because a reassuring label must never rest on a guess.
No model or no risk.json -> no category (the UI and reports say it is not available). A category is a screening aid, never a diagnosis.
"""
import json
import threading
from pathlib import Path

from app.core.config import settings
from app.inference import classifier

CATEGORY = {"low": "Low Risk", "moderate": "Moderate Risk", "high": "High Risk", "review": "Requires Clinical Review"}
RECOMMENDATION = {
    "low": "The model finds a low likelihood of skin-cancer patterns. This is not a clearance: see a clinician if the spot changes, bleeds, itches or does not heal.",
    "moderate": "The model's signals are mixed. A clinician should look at this spot.",
    "high": "The model finds patterns it associates with skin cancer. Please arrange a professional evaluation soon.",
    "review": "The result is not reliable enough to give a risk level. Clinical review is recommended.",
}
_lock = threading.Lock()
_cache: dict = {}


def load_protocol() -> dict | None:
    m = classifier.get_model()
    if m is None:
        return None
    f = Path(settings.model_dir) / m.version / "risk.json"
    try:
        stamp = (m.version, f.stat().st_mtime)
    except OSError:
        return None
    with _lock:
        if _cache.get("stamp") != stamp:
            try:
                _cache.update(stamp=stamp, protocol=json.loads(f.read_text()))
            except (ValueError, OSError):
                _cache.update(stamp=stamp, protocol=None)
        return _cache["protocol"]


def info() -> dict | None:
    p = load_protocol()
    if not p:
        return None
    return {k: p.get(k) for k in ("protocol", "malignant_classes", "target_sensitivity", "high_specificity", "t_low", "t_high", "fitted_on", "performance")}


def assess(pred: dict, quality_label: str | None, lesion_found: bool, protocol: dict | None = None) -> dict | None:
    p = protocol if protocol is not None else load_protocol()
    if not p or not pred:
        return None
    mal = [c for c in p["malignant_classes"] if c in pred["probabilities"]]
    if not mal:
        return None
    p_mal = float(sum(pred["probabilities"][c] for c in mal))
    key = "high" if p_mal >= p["t_high"] else "low" if p_mal < p["t_low"] else "moderate"
    reasons = [f"Estimated likelihood of a skin-cancer pattern ({', '.join(mal)}): {p_mal * 100:.0f}%."]
    if key == "low" and not lesion_found:
        key = "review"
        reasons.append("The lesion could not be located automatically, so a low-risk label would rest on a guess.")
    if quality_label == "acceptable":
        reasons.append("Image quality is only acceptable; a clearer photo may change the result.")
    if pred.get("low_confidence"):
        reasons.append("The model is not confident about the exact diagnosis class.")
    return {"key": key, "category": CATEGORY[key], "recommendation": RECOMMENDATION[key], "p_malignant": round(p_mal, 4),
            "reasons": reasons, "protocol": p.get("protocol", "unversioned")}

