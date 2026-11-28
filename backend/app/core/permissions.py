"""Role permission matrix: who may do what, and which fields each role may see.

Enforced in the API (app/services/views.py shapes every response). The web app mirrors this in
frontend/src/lib/permissions.ts only to decide what to render. Keep the two in step and see
docs/role_permissions.md.
"""
from app.models import User

CAPABILITIES: dict[str, set[str]] = {
    "patient": {"create_case", "upload_image", "view_history"},
    "dermatologist": {"create_case", "upload_image", "view_history", "compare", "add_notes"},
    "researcher": {"view_history", "compare"},
    "ml_engineer": {"view_history", "compare"},
    "admin": {"view_history", "manage_users"},
}


def can(user: User, capability: str) -> bool:
    if capability == "create_for_patient":      # clinicians act for patients only once verified
        return user.role == "dermatologist" and user.is_verified
    return capability in CAPABILITIES.get(user.role, set())


_CASE_ALL = {"case_code", "created_at", "updated_at", "body_location", "patient_age", "patient_gender",
             "medical_history", "known_allergies", "clinical_notes", "owner_name"}

CASE_FIELDS: dict[str, set[str]] = {
    # Patients see the details they entered themselves, never clinician notes or other people's data.
    "patient": {"case_code", "created_at", "updated_at", "body_location", "patient_age", "patient_gender", "medical_history", "known_allergies"},
    "dermatologist": _CASE_ALL,
    # De-identified: no names, ages, history, allergies or notes.
    "researcher": {"case_code", "created_at", "updated_at", "body_location"},
    "ml_engineer": {"case_code", "created_at", "updated_at"},
    "admin": {"case_code", "created_at", "updated_at"},
}

_QUALITY = {"quality_label", "blur_score", "brightness", "contrast", "quality_issues"}
_FILE = {"file_format", "file_size_bytes", "width", "height", "original_filename"}

IMAGE_FIELDS: dict[str, set[str]] = {
    "patient": {"capture_date", "body_location", "analysis_status", "prediction_result", "quality_label", "quality_issues", "created_at", "lesion_info"},
    "dermatologist": {"capture_date", "body_location", "image_source", "analysis_status", "model_version", "prediction_result", "created_at", "lesion_info"} | _QUALITY | _FILE,
    "researcher": {"capture_date", "body_location", "image_source", "analysis_status", "model_version", "prediction_result", "created_at", "lesion_info"} | _QUALITY,
    "ml_engineer": {"image_source", "analysis_status", "model_version", "prediction_result", "created_at", "lesion_info"} | _QUALITY | {"file_format", "file_size_bytes", "width", "height"},
    "admin": {"image_source", "analysis_status", "model_version", "created_at"},
}

# Image files are patient/clinical data: administrators get operational data only.
def can_view_files(user: User) -> bool:
    return user.role != "admin"


# Dashboard breakdowns each role may see.
BREAKDOWNS: dict[str, set[str]] = {
    "patient": {"status", "quality"},
    "dermatologist": {"status", "quality", "body_location", "source", "predicted", "risk", "confidence"},
    "researcher": {"status", "quality", "body_location", "source", "model_version", "predicted", "confidence"},
    "ml_engineer": {"status", "quality", "source", "model_version", "predicted", "confidence"},
    "admin": {"status", "source", "model_version", "users_by_role"},
}

