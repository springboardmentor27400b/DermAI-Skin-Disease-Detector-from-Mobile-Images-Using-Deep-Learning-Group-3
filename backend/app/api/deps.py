from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.core.permissions import can
from app.models import Case, RevokedToken, User
from app.services.access import visible_cases_query

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise cred_exc
    if payload.get("jti") and db.get(RevokedToken, payload["jti"]):       # signed out
        raise cred_exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise cred_exc
    return user


def require_roles(*roles: str) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action.")
        return user

    return checker


def get_case_or_404(case_id: int, db: Session, user: User) -> Case:
    case = db.scalar(visible_cases_query(user).where(Case.id == case_id))
    # Same response for "missing" and "not yours" so IDs cannot be probed.
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    return case


def require_capability(user: User, capability: str) -> None:
    if not can(user, capability):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account type cannot do this.")

