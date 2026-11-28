"""Notification and alert system (brief section 17). Derived on request from analyses the caller may see; nothing extra is stored.

Levels: informational, low, medium, high. There is deliberately no "critical" level: an AI prediction alone is not a confirmed
diagnosis, so wording stays at "clinical review recommended" and never states that a condition was found.
Patients and clinicians get the full set; administrators only see failed analyses; researchers and ML engineers get none.
"""
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Case, ImageRecord, NotificationRead, User
from app.schemas.schemas import NotificationKeys, NotificationOut
from app.services.access import visible_cases_query

router = APIRouter(prefix="/notifications", tags=["notifications"])
FOLLOW_UP_DAYS = 28
RANK = {"high": 3, "medium": 2, "low": 1, "informational": 0}


def _aware(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _pred(img: ImageRecord) -> dict | None:
    try:
        return json.loads(img.prediction_result) if img.prediction_result else None
    except ValueError:
        return None


@router.get("", response_model=list[NotificationOut])
def list_notifications(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ("patient", "dermatologist", "admin"):
        return []
    ids = visible_cases_query(user).with_only_columns(Case.id).scalar_subquery()
    imgs = db.scalars(select(ImageRecord).where(ImageRecord.case_id.in_(ids)).order_by(ImageRecord.created_at.desc()).limit(300)).all()
    out: list[NotificationOut] = []

    def add(img: ImageRecord, kind: str, level: str, title: str, message: str):
        out.append(NotificationOut(key=f"{img.id}-{kind}", level=level, title=title, message=message, case_id=img.case_id,
                                   case_code=img.case_code, image_id=img.id, created_at=_aware(img.created_at)))

    latest_per_case: dict[int, ImageRecord] = {}
    for img in imgs:
        latest_per_case.setdefault(img.case_id, img)
        if img.analysis_status == "failed":
            add(img, "failed", "medium", "Analysis failed", "The analysis could not be completed. Try re-analysing the image.")
        if user.role == "admin":
            continue
        if img.analysis_status == "rejected_quality":
            add(img, "quality", "medium", "Poor image quality", "This photo was not analysed because its quality is too low. Please retake it in even light, in focus.")
            continue
        pr = _pred(img)
        if img.analysis_status != "completed" or not pr:
            continue
        key = (pr.get("risk") or {}).get("key")
        if key == "high":
            add(img, "risk", "high", "Clinical review recommended",
                "The AI-assisted analysis found patterns that a clinician should look at soon. This is not a diagnosis.")
        elif key == "review":
            add(img, "risk", "medium", "Clinical review recommended", "The AI-assisted result is not reliable enough to give a risk level. A clinician should look at this spot.")
        if pr.get("low_confidence"):
            add(img, "conf", "low", "Low-confidence prediction", "The model is not confident about this image. Treat the result with extra caution.")
        add(img, "done", "informational", "Analysis completed", "The AI-assisted analysis is ready to view.")

    if user.role != "admin":
        now = datetime.now(timezone.utc)
        for img in latest_per_case.values():                       # follow-up reminders: unresolved concern, no newer photo
            pr = _pred(img)
            key = ((pr or {}).get("risk") or {}).get("key")
            when = _aware(img.created_at)
            if key in ("moderate", "high", "review") and when and now - when >= timedelta(days=FOLLOW_UP_DAYS):
                add(img, "followup", "low", "Follow-up suggested", f"No newer photo has been added for this case in {FOLLOW_UP_DAYS} days. Consider a follow-up image or a clinical visit.")

    seen = set(db.scalars(select(NotificationRead.key).where(NotificationRead.user_id == user.id)).all())
    for n in out:
        n.read = n.key in seen
    out.sort(key=lambda n: (n.created_at or datetime.min.replace(tzinfo=timezone.utc), RANK[n.level]), reverse=True)
    return out[:min(limit, 200)]


@router.post("/read", status_code=204)
def mark_read(body: NotificationKeys, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mark notifications as read for the caller only. Unknown keys are harmless (they just never match an alert)."""
    have = set(db.scalars(select(NotificationRead.key).where(NotificationRead.user_id == user.id)).all())
    for k in set(body.keys) - have:
        db.add(NotificationRead(user_id=user.id, key=k))
    db.commit()

