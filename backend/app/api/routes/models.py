import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.inference import classifier, explain, risk, segmenter
from app.models import ImageRecord, User
from app.models.enums import AnalysisStatus
from app.preprocessing.pipeline import to_rgb_array
from app.preprocessing.validation import ImageValidationError, validate_image_bytes
from app.services import analysis, storage
from app.services.audit import log_action

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/active")
def active_model(user: User = Depends(get_current_user)):
    """Deployed classifier. Evaluation metrics and protocol details are hidden from patients."""
    out = classifier.describe(include_evaluation=user.role != "patient")
    if out.get("available"):
        out["explainability_available"] = explain.available()
        if user.role != "patient":
            out["risk_protocol"] = risk.info()
    return out


@router.get("/versions")
def versions(admin: User = Depends(require_roles("admin"))):
    """Model registry: every version in the models folder with its training and evaluation summary."""
    out, active = [], classifier.active_version()
    for v in classifier.list_versions():
        d = Path(settings.model_dir) / v
        try:
            meta = json.loads((d / "meta.json").read_text())
        except (ValueError, OSError):
            continue
        ev = meta.get("evaluation") or {}
        out.append({"version": v, "arch": meta.get("arch"), "trained_at": meta.get("created_at"), "dataset": meta.get("dataset"),
                    "preprocessing": meta.get("preprocessing"), "macro_f1": ev.get("macro_f1"), "balanced_accuracy": ev.get("balanced_accuracy"),
                    "macro_auc": ev.get("macro_auc_ovr"), "ece": ev.get("ece"), "final_model": meta.get("final_model"),
                    "members": [m.get("arch") for m in meta.get("members") or []] or None,
                    "explainability": bool(meta.get("explain")), "risk_protocol": (d / "risk.json").is_file(), "active": v == active,
                    "training": {"best_epoch": meta.get("best_epoch"), "folds_sha256": meta.get("folds_sha256"), "n_train": meta.get("n_train"),
                                 **{k: (meta.get("args") or {}).get(k) for k in ("epochs", "lr", "batch", "imbalance", "aug", "weight_decay", "seed")}}})
    return out


@router.post("/activate")
def activate(version: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    """Deploy (or roll back to) a version. Existing results keep the version that produced them; use /reanalyze to refresh them."""
    if settings.active_model:
        raise HTTPException(409, "The active model is pinned by the ACTIVE_MODEL environment variable; unset it to switch versions here.")
    if version not in classifier.list_versions():
        raise HTTPException(404, "Unknown model version.")
    previous = classifier.active_version()
    (Path(settings.model_dir) / "active.json").write_text(json.dumps({"version": version}))
    classifier.reload(); segmenter.reload()
    log_action(db, "model.activate", admin, f"model:{version}", f"previous={previous}", request)
    return {**classifier.describe(include_evaluation=True), "previous": previous}


@router.post("/reload")
def reload_models(admin: User = Depends(require_roles("admin"))):
    classifier.reload(); segmenter.reload()
    return {**classifier.describe(include_evaluation=True), "segmentation": segmenter.info()}


@router.post("/reanalyze")
def reanalyze(all_images: bool = False, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    """Run the active model over stored images that are still pending (or over every analysable image)."""
    if not classifier.is_available():
        return {"processed": 0, "failed": 0, "detail": "No classifier is deployed."}
    wanted = [AnalysisStatus.pending.value, AnalysisStatus.failed.value] + ([AnalysisStatus.completed.value] if all_images else [])
    done = failed = 0
    for img in db.scalars(select(ImageRecord).where(ImageRecord.analysis_status.in_(wanted))).all():
        try:
            with open(img.stored_path, "rb") as f:
                rgb = to_rgb_array(validate_image_bytes(f.read()).image)
            a = analysis.analyze(rgb, img.quality_label)
            storage.remove_files(img.processed_path, img.lesion_path, img.cam_path, img.saliency_path)
            img.processed_path, img.lesion_path, img.cam_path, img.saliency_path = analysis.save_artifacts(img.case_id, a)
            img.lesion_info = json.dumps(a.lesion.info())
            img.analysis_status, img.model_version, img.prediction_result = a.status.value, a.model_version, analysis.prediction_json(a)
            db.commit(); done += 1
        except (OSError, ImageValidationError):
            failed += 1
    return {"processed": done, "failed": failed}

