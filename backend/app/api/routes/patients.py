from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_capability
from app.db.session import get_db
from app.models import User
from app.schemas.schemas import PatientBrief

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientBrief])
def search_patients(q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Verified clinicians pick a patient to open a case for."""
    require_capability(user, "create_for_patient")
    stmt = select(User).where(User.role == "patient", User.is_active.is_(True))
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    return db.scalars(stmt.order_by(User.full_name).limit(25)).all()

