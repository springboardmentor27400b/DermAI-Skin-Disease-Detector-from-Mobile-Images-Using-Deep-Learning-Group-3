import json
from datetime import date

import cv2
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_case_or_404, get_current_user, require_capability
from app.core.config import settings
from app.db.session import get_db
from app.core.permissions import IMAGE_FIELDS, can_view_files
from app.models import Case, ImageRecord, User
from app.models.enums import AnalysisStatus, ImageSource
from app.preprocessing.pipeline import save_preview, to_rgb_array
from app.preprocessing.quality import assess_quality
from app.preprocessing.validation import ImageValidationError, validate_image_bytes
from app.schemas.schemas import HistoryView, ImageView, QualityOut
from app.services import analysis, storage
from app.services.access import can_delete, visible_cases_query
from app.services.audit import log_action
from app.services.views import history_view, image_view

router = APIRouter(tags=["images"])


async def _read_limited(file: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
    return data


@router.get("/images/quality-thresholds")
def quality_thresholds(user: User = Depends(get_current_user)):
    """Cut-offs the quality check uses, so the UI draws the same ticks as the server applies."""
    from app.preprocessing import quality as q
    return {"blur": [q.BLUR_POOR, q.BLUR_ACCEPTABLE], "contrast": [q.CONTRAST_POOR, q.CONTRAST_ACCEPTABLE],
            "brightness_dark": [q.DARK_POOR, q.DARK_ACCEPTABLE], "brightness_bright": [q.BRIGHT_ACCEPTABLE, q.BRIGHT_POOR]}


@router.post("/images/check-quality", response_model=QualityOut)
async def check_quality(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Quality check only (nothing is stored). Supports the capture -> quality check -> confirm -> upload flow."""
    require_capability(user, "upload_image")
    data = await _read_limited(file)
    try:
        v = validate_image_bytes(data)
    except ImageValidationError as e:
        raise HTTPException(422, str(e))
    q = assess_quality(to_rgb_array(v.image))
    return QualityOut(**q.as_dict(), width=v.width, height=v.height, acceptable_for_analysis=q.label != "poor")


@router.post("/cases/{case_id}/images", response_model=ImageView, status_code=201)
async def upload_image(
    case_id: int,
    request: Request,
    file: UploadFile = File(...),
    image_source: ImageSource = Form(ImageSource.gallery),
    body_location: str | None = Form(None),
    capture_date: date | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_capability(user, "upload_image")
    case = get_case_or_404(case_id, db, user)
    data = await _read_limited(file)
    try:
        v = validate_image_bytes(data)
    except ImageValidationError as e:
        raise HTTPException(422, str(e))

    rgb = to_rgb_array(v.image)
    quality = assess_quality(rgb)

    stored = storage.save_original(case.id, data, v.format)
    processed_path = lesion_path = cam_path = saliency_path = lesion_info = prediction = model_version = None
    status = AnalysisStatus.rejected_quality
    if quality.label != "poor":
        a = await run_in_threadpool(analysis.analyze, rgb, quality.label)
        processed_path, lesion_path, cam_path, saliency_path = analysis.save_artifacts(case.id, a)
        lesion_info, prediction, model_version = json.dumps(a.lesion.info()), analysis.prediction_json(a), a.model_version
        status = a.status
        if not a.lesion.found:                                   # lesion visibility: informational, the label is unchanged
            quality.issues.append("The lesion could not be located automatically. Keep it in the centre, in focus, with plain skin around it.")

    h, w = rgb.shape[:2]
    rec = ImageRecord(
        case_id=case.id,
        original_filename=storage.safe_filename(file.filename or "upload"),
        stored_path=stored,
        processed_path=processed_path,
        lesion_path=lesion_path,
        cam_path=cam_path,
        saliency_path=saliency_path,
        lesion_info=lesion_info,
        model_version=model_version,
        prediction_result=prediction,
        image_source=image_source.value,
        capture_date=capture_date or date.today(),
        body_location=body_location or case.body_location,
        file_format=v.format,
        file_size_bytes=v.size_bytes,
        width=w, height=h,
        quality_label=quality.label,
        blur_score=quality.blur_score,
        brightness=quality.brightness,
        contrast=quality.contrast,
        quality_issues=json.dumps(quality.issues),
        analysis_status=status.value,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    log_action(db, "image.upload", user, f"image:{rec.id}", f"case:{case.id} quality={quality.label}", request)
    return image_view(rec, user)


@router.get("/cases/{case_id}/images", response_model=list[ImageView])
def list_images(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [image_view(i, user) for i in get_case_or_404(case_id, db, user).images]


@router.get("/images/history", response_model=list[HistoryView])
def image_history(
    date_from: date | None = None,
    date_to: date | None = None,
    analysis_status: str | None = Query(None),
    quality: str | None = Query(None),
    image_source: str | None = Query(None),
    model_version: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Previous analyses across the cases the caller may see, newest first.
    Filters on fields a role cannot see are ignored, so they cannot be used to infer hidden values."""
    require_capability(user, "view_history")
    visible = IMAGE_FIELDS[user.role]
    ids = visible_cases_query(user).with_only_columns(Case.id).scalar_subquery()
    q = select(ImageRecord).where(ImageRecord.case_id.in_(ids))
    if "capture_date" in visible:
        if date_from:
            q = q.where(ImageRecord.capture_date >= date_from)
        if date_to:
            q = q.where(ImageRecord.capture_date <= date_to)
    if analysis_status:
        q = q.where(ImageRecord.analysis_status == analysis_status)
    if quality and "quality_label" in visible:
        q = q.where(ImageRecord.quality_label == quality)
    if image_source and "image_source" in visible:
        q = q.where(ImageRecord.image_source == image_source)
    if model_version and "model_version" in visible:
        q = q.where(ImageRecord.model_version == model_version)
    rows = db.scalars(q.order_by(ImageRecord.created_at.desc()).offset(skip).limit(min(limit, 500))).all()
    return [history_view(r, user) for r in rows]


@router.get("/images/{image_id}", response_model=HistoryView)
def get_image(image_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """One analysis, shaped for the caller's role (drives the analysis screen)."""
    require_capability(user, "view_history")
    img = db.get(ImageRecord, image_id)
    if not img:
        raise HTTPException(404, "Image not found.")
    get_case_or_404(img.case_id, db, user)     # authorisation (same 404 for missing and not-yours)
    return history_view(img, user)


@router.get("/images/{image_id}/file")
def get_image_file(
    image_id: int,
    variant: str = "original",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    img = db.get(ImageRecord, image_id)
    if not img:
        raise HTTPException(404, "Image not found.")
    get_case_or_404(img.case_id, db, user)  # authorisation
    if not can_view_files(user):
        raise HTTPException(403, "Your account type cannot view image files.")
    path = {"processed": img.processed_path, "lesion": img.lesion_path, "cam": img.cam_path, "saliency": img.saliency_path}.get(variant, img.stored_path)
    if not path:
        raise HTTPException(404, "This variant is not available (image was rejected for quality).")
    media = "image/png" if path.endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=300"})


@router.post("/images/{image_id}/analyze", response_model=ImageView)
async def reanalyze_image(image_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Re-run lesion detection and classification with the currently deployed model."""
    require_capability(user, "upload_image")
    img = db.get(ImageRecord, image_id)
    if not img:
        raise HTTPException(404, "Image not found.")
    case = get_case_or_404(img.case_id, db, user)
    if img.quality_label == "poor":
        raise HTTPException(409, "This image was rejected for quality and cannot be analysed. Upload a clearer photo.")
    with open(img.stored_path, "rb") as f:
        rgb = to_rgb_array(validate_image_bytes(f.read()).image)
    a = await run_in_threadpool(analysis.analyze, rgb, img.quality_label)
    storage.remove_files(img.processed_path, img.lesion_path, img.cam_path, img.saliency_path)
    img.processed_path, img.lesion_path, img.cam_path, img.saliency_path = analysis.save_artifacts(case.id, a)
    img.lesion_info, img.prediction_result, img.model_version = json.dumps(a.lesion.info()), analysis.prediction_json(a), a.model_version
    img.analysis_status = a.status.value
    db.commit(); db.refresh(img)
    log_action(db, "image.analyze", user, f"image:{img.id}", f"status={a.status.value} model={a.model_version}", request)
    return image_view(img, user)


@router.delete("/images/{image_id}", status_code=204)
def delete_image(image_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    img = db.get(ImageRecord, image_id)
    if not img:
        raise HTTPException(404, "Image not found.")
    case = get_case_or_404(img.case_id, db, user)
    if not can_delete(user, case):
        raise HTTPException(403, "Only the person who owns or opened this case can delete its images.")
    storage.remove_files(img.stored_path, img.processed_path, img.lesion_path, img.cam_path, img.saliency_path)
    db.delete(img)
    db.commit()
    log_action(db, "image.delete", user, f"image:{image_id}", request=request)

