import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "jti": uuid.uuid4().hex,        # lets a token be revoked at sign-out
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def password_strength_error(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password.lower() == password or password.upper() == password:
        return "Password must mix upper and lower case letters."
    if not any(c.isdigit() for c in password):
        return "Password must contain a digit."
    return None

