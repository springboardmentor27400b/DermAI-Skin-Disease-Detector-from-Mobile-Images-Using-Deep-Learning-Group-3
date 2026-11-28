"""Lesion detection -> ROI preprocessing -> classification -> risk category -> Grad-CAM, shared by upload and re-analysis."""
import json
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import settings
from app.inference import classifier, explain, risk
from app.models.enums import AnalysisStatus
from app.preprocessing.lesion import LesionResult, detect_lesion, overlay
from app.preprocessing.pipeline import PreprocessResult, preprocess, save_preview
from app.services import storage


@dataclass
class Analysis:
    lesion: LesionResult
    pre: PreprocessResult
    overlay_rgb: np.ndarray
    status: AnalysisStatus
    model_version: str | None = None
    prediction: dict | None = None
    error: str | None = None
    cam_rgb: np.ndarray | None = None
    sal_rgb: np.ndarray | None = None


def analyze(rgb: np.ndarray, quality_label: str) -> Analysis:
    lesion = detect_lesion(rgb)
    flags = classifier.preprocessing_flags()          # same recipe the model was trained on
    pre = preprocess(rgb, flags["size"], lesion=lesion if flags["lesion_roi"] else None, enhance=flags["enhance"], remove_hair_artifacts=flags["hair_removal"], roi_min_frac=flags["roi_min"])
    out = Analysis(lesion, pre, overlay(rgb, lesion, roi_min_frac=flags["roi_min"]), AnalysisStatus.pending)
    if not classifier.is_available():
        return out
    caveats = []
    if quality_label == "acceptable":
        caveats.append("Image quality is only acceptable; a clearer photo may change the result.")
    if lesion.method == "rejected_touches_edge":
        caveats.append("A spot touches the edge of the photo and may be cut off; retake the photo with the lesion fully in frame.")
    if not lesion.found and flags["lesion_roi"]:
        caveats.append("The lesion could not be located automatically; the centre of the photo was analysed.")
    elif lesion.lesion_count > 1 and flags["lesion_roi"]:
        caveats.append(f"{lesion.lesion_count} separate spots were detected; only the one nearest the centre was analysed.")
    try:
        out.prediction = classifier.predict(pre.preview_rgb, caveats)
        out.model_version = out.prediction["model"]["version"]
        out.status = AnalysisStatus.completed
    except Exception as e:                     # keep the upload; mark the analysis as failed
        out.status, out.error = AnalysisStatus.failed, str(e)[:200]
        return out

    pred = out.prediction
    try:                                       # Milestone 3: risk category (never blocks the result)
        pred["risk"] = risk.assess(pred, quality_label, lesion.found)
    except Exception:
        pred["risk"] = None
    try:                                       # Milestone 3: attention map for the predicted class
        if explain.available():
            idx = list(pred["probabilities"]).index(pred["label"])
            heat = explain.heatmap(pre.preview_rgb, idx)
            if heat is not None:
                out.cam_rgb = explain.overlay(pre.preview_rgb, heat)
                pred["explain"] = {"method": "Grad-CAM++" if settings.explain_method == "gradcampp" else "Grad-CAM", "target": pred["label"],
                                   **(explain.lesion_overlap(heat, lesion, rgb.shape[:2], flags["lesion_roi"], flags["roi_min"]) or {})}
                try:                               # extra pass on the mirrored photo; never blocks the result
                    st = explain.stability(pre.preview_rgb, idx, heat)
                    if st is not None:
                        pred["explain"]["stability"] = round(st, 3)
                except Exception:
                    pass
    except Exception:
        out.cam_rgb = None
    pred.setdefault("explain", None)
    try:                                       # gradient saliency on the full model (independent of the Grad-CAM split)
        sal = explain.saliency(pre.preview_rgb, list(pred["probabilities"]).index(pred["label"]))
        if sal is not None:
            out.sal_rgb = explain.saliency_overlay(pre.preview_rgb, sal)
            pred["saliency"] = {"method": "Gradient saliency", "target": pred["label"]}
    except Exception:
        out.sal_rgb = None
    pred.setdefault("saliency", None)
    return out


def save_artifacts(case_id: int, a: Analysis) -> tuple[str, str, str | None, str | None]:
    """Write the preprocessed image, lesion overlay and (when available) attention and saliency maps; returns their paths."""
    processed = storage.processed_path_for(case_id)
    save_preview(a.pre.preview_rgb, processed)
    lesion = storage.lesion_path_for(case_id)
    cv2.imwrite(lesion, cv2.cvtColor(a.overlay_rgb, cv2.COLOR_RGB2BGR))
    cam = None
    if a.cam_rgb is not None:
        cam = storage.cam_path_for(case_id)
        cv2.imwrite(cam, cv2.cvtColor(a.cam_rgb, cv2.COLOR_RGB2BGR))
    sal = None
    if a.sal_rgb is not None:
        sal = storage.saliency_path_for(case_id)
        cv2.imwrite(sal, cv2.cvtColor(a.sal_rgb, cv2.COLOR_RGB2BGR))
    return processed, lesion, cam, sal


def prediction_json(a: Analysis) -> str | None:
    return json.dumps(a.prediction) if a.prediction else None

