from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log_action(
    db: Session,
    action: str,
    user: User | None = None,
    resource: str | None = None,
    detail: str | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource=resource,
            detail=detail,
            ip_address=request.client.host if request and request.client else None,
        )
    )
    db.commit()

