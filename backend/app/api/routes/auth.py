from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

import jwt

from app.api.deps import get_current_user, oauth2_scheme
from app.core.ratelimit import login_limiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_strength_error,
    verify_password,
)
from app.db.session import get_db
from app.models import RevokedToken, User
from app.schemas.schemas import ROLE_FIELDS, PasswordChange, Token, UserCreate, UserOut, UserUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: UserCreate, request: Request, db: Session = Depends(get_db)):
    if err := password_strength_error(body.password):
        raise HTTPException(422, err)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        hashed_password=hash_password(body.password),
        role=body.role,
        is_verified=body.role != "dermatologist",   # clinicians wait for admin verification
        **body.profile_dict(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, "user.register", user, f"user:{user.id}", request=request)
    return user


@router.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '?'}|{form.username.lower()}"
    wait = login_limiter.blocked(key)
    if wait:                                         # checked before the password, so a correct guess after lockout is also refused
        log_action(db, "auth.login_blocked", None, detail=form.username[:120], request=request)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many failed sign-in attempts. Try again in about {wait // 60 + 1} minutes.",
                            headers={"Retry-After": str(wait)})
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not user.is_active or not verify_password(form.password, user.hashed_password):
        login_limiter.fail(key)
        log_action(db, "auth.login_failed", None, detail=form.username[:120], request=request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    login_limiter.reset(key)
    log_action(db, "auth.login", user, f"user:{user.id}", request=request)
    return Token(access_token=create_access_token(str(user.id), user.role), user=user)


@router.post("/logout", status_code=204)
def logout(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Revoke the presented token so it stops working before it expires. Expired revocations are cleaned up here."""
    now = datetime.now(timezone.utc)
    try:
        p = decode_access_token(token)
        if p.get("jti") and not db.get(RevokedToken, p["jti"]):
            db.add(RevokedToken(jti=p["jti"], expires_at=datetime.fromtimestamp(p["exp"], timezone.utc)))
    except jwt.PyJWTError:
        pass
    for old in db.scalars(select(RevokedToken).where(RevokedToken.expires_at < now)).all():
        db.delete(old)
    db.commit()
    log_action(db, "auth.logout", user, f"user:{user.id}", request=request)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = body.model_dump(exclude_unset=True)
    if name := data.pop("full_name", None):
        user.full_name = name.strip()
    allowed = ROLE_FIELDS.get(user.role, set())
    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "license_number" and user.role == "dermatologist" and v != user.license_number:
            user.is_verified = False        # a changed licence must be re-verified
        if k == "research_consent":
            if v is not None:
                user.research_consent = bool(v)
            continue
        setattr(user, k, v or None)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=204)
def change_password(
    body: PasswordChange, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect.")
    if err := password_strength_error(body.new_password):
        raise HTTPException(422, err)
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    log_action(db, "auth.password_changed", user, f"user:{user.id}", request=request)
