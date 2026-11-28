import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_case_or_404, get_current_user, require_capability
from app.core.permissions import BREAKDOWNS, can
from app.db.session import get_db
from app.models import Case, CaseNote, ImageRecord, User
from app.schemas.schemas import (
    CaseCreate, CaseSummaryView, CaseUpdate, CaseView, DashboardStats, NoteCreate, NoteOut,
)
from app.services import storage
from app.services.access import can_delete, visible_cases_query
from app.services.audit import log_action
from app.services.views import case_view, summary_view

router = APIRouter(prefix="/cases", tags=["cases"])

# Fields a patient may fill in about their own case. Clinical notes belong to clinicians.
PATIENT_CASE_FIELDS = {"patient_age", "patient_gender", "medical_history", "known_allergies", "body_location"}


def _new_case_code() -> str:
    return f"DRM-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"


@router.post("", response_model=CaseView, status_code=201)
def create_case(body: CaseCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_capability(user, "create_case")
    data = body.model_dump(exclude={"patient_id"})
    owner_id, created_by = user.id, None

    if user.role == "patient":
        data = {k: v for k, v in data.items() if k in PATIENT_CASE_FIELDS}
        if body.patient_id not in (None, user.id):
            raise HTTPException(403, "Patients can only create cases for themselves.")
    elif body.patient_id is not None:
        require_capability(user, "create_for_patient")
        patient = db.get(User, body.patient_id)
        if not patient or patient.role != "patient" or not patient.is_active:
            raise HTTPException(404, "Patient not found.")
        owner_id, created_by = patient.id, user.id

    case = Case(case_code=_new_case_code(), owner_id=owner_id, created_by_id=created_by, **data)
    db.add(case)
    db.commit()
    db.refresh(case)
    log_action(db, "case.create", user, f"case:{case.id}", f"on_behalf_of={owner_id}" if created_by else None, request)
    return case_view(case, user)


@router.get("", response_model=list[CaseSummaryView])
def list_cases(db: Session = Depends(get_db), user: User = Depends(get_current_user), skip: int = 0, limit: int = 50):
    q = visible_cases_query(user).order_by(Case.created_at.desc()).offset(skip).limit(min(limit, 200))
    return [summary_view(c, user) for c in db.scalars(q).all()]


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = visible_cases_query(user).with_only_columns(Case.id).scalar_subquery()
    total_cases = db.scalar(select(func.count()).select_from(visible_cases_query(user).subquery())) or 0
    images = db.scalars(select(ImageRecord).where(ImageRecord.case_id.in_(ids))).all()

    def pred(i):
        try:
            return json.loads(i.prediction_result) if i.prediction_result else None
        except ValueError:
            return None

    def conf_bucket(i):
        c = (pred(i) or {}).get("confidence")
        if c is None:
            return None
        return "under 50%" if c < 0.5 else "50-70%" if c < 0.7 else "70-90%" if c < 0.9 else "90% or more"

    getters = {
        "confidence": conf_bucket,
        "predicted": lambda i: (pred(i) or {}).get("label_name"),
        "risk": lambda i: ((pred(i) or {}).get("risk") or {}).get("category"),
        "status": lambda i: i.analysis_status,
        "quality": lambda i: i.quality_label,
        "source": lambda i: i.image_source,
        "model_version": lambda i: i.model_version or "unversioned",
        "body_location": lambda i: i.body_location or "unspecified",
    }
    out: dict[str, dict[str, int]] = {}
    for key in BREAKDOWNS[user.role] & getters.keys():
        counts: dict[str, int] = {}
        for i in images:
            v = getters[key](i)
            if v is None:                       # e.g. images without a prediction are not counted under 'predicted'
                continue
            counts[v] = counts.get(v, 0) + 1
        out[key] = counts
    if "users_by_role" in BREAKDOWNS[user.role]:
        out["users_by_role"] = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    return DashboardStats(total_cases=total_cases, total_images=len(images), breakdowns=out)


@router.get("/{case_id}", response_model=CaseView)
def get_case(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return case_view(get_case_or_404(case_id, db, user), user)


@router.patch("/{case_id}", response_model=CaseView)
def update_case(case_id: int, body: CaseUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = get_case_or_404(case_id, db, user)
    if user.role not in ("patient", "dermatologist"):
        raise HTTPException(403, "Your account type cannot edit cases.")
    data = body.model_dump(exclude_unset=True)
    if user.role == "patient":
        data = {k: v for k, v in data.items() if k in PATIENT_CASE_FIELDS}
    for k, v in data.items():
        setattr(case, k, v)
    db.commit()
    db.refresh(case)
    log_action(db, "case.update", user, f"case:{case.id}", request=request)
    return case_view(case, user)


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = get_case_or_404(case_id, db, user)
    if not can_delete(user, case):
        raise HTTPException(403, "Only the person who owns or opened this case can delete it.")
    for img in case.images:
        storage.remove_files(img.stored_path, img.processed_path, img.lesion_path, img.cam_path, img.saliency_path)
    db.delete(case)
    db.commit()
    log_action(db, "case.delete", user, f"case:{case_id}", request=request)


@router.get("/{case_id}/notes", response_model=list[NoteOut])
def list_notes(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_capability(user, "add_notes")
    return get_case_or_404(case_id, db, user).notes


@router.post("/{case_id}/notes", response_model=NoteOut, status_code=201)
def add_note(case_id: int, body: NoteCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_capability(user, "add_notes")
    case = get_case_or_404(case_id, db, user)
    note = CaseNote(case_id=case.id, author_id=user.id, text=body.text)
    db.add(note)
    db.commit()
    db.refresh(note)
    log_action(db, "case.note_add", user, f"case:{case.id}", request=request)
    return note

