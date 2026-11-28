"""Which cases a user may open. Single source of truth for list, detail, image and history queries."""
from sqlalchemy import select

from app.core.config import settings
from app.models import Case, User


def sees_everything(user: User) -> bool:
    return user.role == "admin" or (user.role == "dermatologist" and user.is_verified)


def visible_cases_query(user: User):
    q = select(Case)
    if sees_everything(user):
        return q
    if user.role in ("researcher", "ml_engineer"):
        if not settings.research_requires_consent:
            return q
        opted_in = select(User.id).where(User.role == "patient", User.research_consent.is_(True))
        return q.where(Case.owner_id.in_(opted_in))
    return q.where(Case.owner_id == user.id)


def can_delete(user: User, case: Case) -> bool:
    return user.role in ("patient", "dermatologist") and user.id in (case.owner_id, case.created_by_id)

