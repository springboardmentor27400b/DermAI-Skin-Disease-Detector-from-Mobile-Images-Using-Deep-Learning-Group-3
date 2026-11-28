from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.security import hash_password, password_strength_error
from app.db.session import get_db
from app.models import AuditLog, User
from app.schemas.schemas import AdminUserCreate, AuditLogOut, UserOut
from app.services.audit import log_action

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_roles("admin")


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: AdminUserCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    if err := password_strength_error(body.password):
        raise HTTPException(422, err)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=email, full_name=body.full_name.strip(), hashed_password=hash_password(body.password), role=body.role, is_verified=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, "admin.user_create", admin, f"user:{user.id}", f"role={user.role}", request)
    return user


@router.patch("/users/{user_id}/active", response_model=UserOut)
def set_active(user_id: int, active: bool, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    if user.id == admin.id and not active:
        raise HTTPException(400, "You cannot deactivate your own account.")
    user.is_active = active
    db.commit()
    db.refresh(user)
    log_action(db, "admin.user_active", admin, f"user:{user.id}", f"active={active}", request)
    return user


@router.patch("/users/{user_id}/verify", response_model=UserOut)
def set_verified(user_id: int, verified: bool, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    if user.role != "dermatologist":
        raise HTTPException(400, "Only clinician accounts need verification.")
    user.is_verified = verified
    db.commit()
    db.refresh(user)
    log_action(db, "admin.user_verify", admin, f"user:{user.id}", f"verified={verified}", request)
    return user


@router.get("/audit-logs", response_model=list[AuditLogOut])
def audit_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(skip).limit(min(limit, 500))).all()

