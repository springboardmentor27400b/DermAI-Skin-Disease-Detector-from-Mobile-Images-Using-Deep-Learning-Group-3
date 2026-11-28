"""Build role-appropriate responses. Fields a role may not see are never sent."""
from app.core.permissions import CASE_FIELDS, IMAGE_FIELDS, can
from app.models import Case, ImageRecord, User
from app.schemas.schemas import (
    CasePermissions, CaseSummaryView, CaseView, HistoryView, ImageOut, ImageView, NoteOut,
)
from app.services.access import can_delete

_ALWAYS = {"id", "case_id"}


def image_view(img: ImageRecord, user: User) -> ImageView:
    full = ImageOut.model_validate(img).model_dump()
    allowed = IMAGE_FIELDS[user.role] | _ALWAYS
    return ImageView(**{k: v for k, v in full.items() if k in allowed})


def history_view(img: ImageRecord, user: User) -> HistoryView:
    base = image_view(img, user).model_dump()
    owner = img.owner_name if "owner_name" in CASE_FIELDS[user.role] else None
    return HistoryView(**base, case_code=img.case_code, owner_name=owner)


def _case_fields(case: Case, user: User) -> dict:
    allowed = CASE_FIELDS[user.role]
    return {f: getattr(case, f) for f in allowed if f != "owner_name"} | (
        {"owner_name": case.owner_name} if "owner_name" in allowed else {}
    )


def case_view(case: Case, user: User) -> CaseView:
    is_writer = user.role in ("patient", "dermatologist")
    perms = CasePermissions(
        edit=is_writer,
        delete=can_delete(user, case),
        upload=can(user, "upload_image"),
        add_notes=can(user, "add_notes"),
    )
    notes = [NoteOut.model_validate(n) for n in case.notes] if can(user, "add_notes") else []
    return CaseView(
        id=case.id,
        **_case_fields(case, user),
        images=[image_view(i, user) for i in case.images],
        notes=notes,
        permissions=perms,
    )


def summary_view(case: Case, user: User) -> CaseSummaryView:
    fields = _case_fields(case, user)
    latest = case.images[-1] if case.images else None
    sees_quality = "quality_label" in IMAGE_FIELDS[user.role]
    return CaseSummaryView(
        id=case.id,
        case_code=case.case_code,
        created_at=fields.get("created_at"),
        owner_name=fields.get("owner_name"),
        body_location=fields.get("body_location"),
        patient_age=fields.get("patient_age"),
        patient_gender=fields.get("patient_gender"),
        image_count=len(case.images),
        latest_quality=latest.quality_label if latest and sees_quality else None,
        latest_status=latest.analysis_status if latest else None,
    )

