import json
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, EmailStr, Field, field_validator, model_validator

Gender = Literal["female", "male", "other", "unknown"]

# Which profile fields each role may store (anything else is dropped).
ROLE_FIELDS: dict[str, set[str]] = {
    "patient": {"age", "gender", "medical_history", "known_allergies", "research_consent"},
    "dermatologist": {"institution", "license_number", "specialization"},
    "researcher": {"institution", "research_area", "orcid"},
    "ml_engineer": {"institution"},
    "admin": {"institution"},
}


class ProfileFields(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    gender: Gender | None = None
    medical_history: str | None = Field(default=None, max_length=4000)
    known_allergies: str | None = Field(default=None, max_length=2000)
    institution: str | None = Field(default=None, max_length=160)
    license_number: str | None = Field(default=None, max_length=64)
    specialization: str | None = Field(default=None, max_length=120)
    research_area: str | None = Field(default=None, max_length=200)
    orcid: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    research_consent: bool | None = None


class UserCreate(ProfileFields):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["patient", "dermatologist", "researcher"] = "patient"

    @model_validator(mode="after")
    def _role_requirements(self):
        if self.role == "dermatologist" and not (self.institution and self.license_number):
            raise ValueError("Clinicians must provide their institution and licence / registration number.")
        if self.role == "researcher" and not self.institution:
            raise ValueError("Researchers must provide their institution.")
        return self

    def profile_dict(self) -> dict[str, Any]:
        allowed = ROLE_FIELDS[self.role]
        return {k: v for k, v in self.model_dump(include=set(ProfileFields.model_fields)).items() if k in allowed and v not in (None, "")}


class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["patient", "dermatologist", "researcher", "ml_engineer", "admin"]


class UserUpdate(ProfileFields):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str   # plain str on output: stored value was already validated on input
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    age: int | None = None
    gender: str | None = None
    medical_history: str | None = None
    known_allergies: str | None = None
    institution: str | None = None
    license_number: str | None = None
    specialization: str | None = None
    research_area: str | None = None
    orcid: str | None = None
    research_consent: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CaseBase(BaseModel):
    patient_age: int | None = Field(default=None, ge=0, le=120)
    patient_gender: Gender | None = None
    medical_history: str | None = Field(default=None, max_length=4000)
    known_allergies: str | None = Field(default=None, max_length=2000)
    clinical_notes: str | None = Field(default=None, max_length=4000)
    body_location: str | None = Field(default=None, max_length=64)


class CaseCreate(CaseBase):
    patient_id: int | None = None   # clinicians: open the case on behalf of this patient


class CaseUpdate(CaseBase):
    pass


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    original_filename: str
    image_source: str
    capture_date: date | None
    body_location: str | None
    file_format: str
    file_size_bytes: int
    width: int
    height: int
    quality_label: str
    blur_score: float
    brightness: float
    contrast: float
    quality_issues: list[str] = []
    analysis_status: str
    model_version: str | None
    prediction_result: dict | None = None
    lesion_info: dict | None = None
    created_at: datetime

    @field_validator("quality_issues", mode="before")
    @classmethod
    def _parse_issues(cls, v):
        return json.loads(v) if isinstance(v, str) else (v or [])

    @field_validator("prediction_result", "lesion_info", mode="before")
    @classmethod
    def _parse_pred(cls, v):
        return json.loads(v) if isinstance(v, str) and v else (v or None)


class HistoryItem(ImageOut):
    case_code: str
    owner_name: str


class NoteCreate(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    author_id: int
    author_name: str
    author_role: str
    text: str
    created_at: datetime


class CaseOut(CaseBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_code: str
    owner_id: int
    owner_name: str
    created_at: datetime
    updated_at: datetime
    images: list[ImageOut] = []
    notes: list[NoteOut] = []


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_code: str
    owner_name: str
    body_location: str | None
    patient_age: int | None
    patient_gender: str | None
    created_at: datetime
    image_count: int = 0
    latest_quality: str | None = None
    latest_status: str | None = None


class QualityOut(BaseModel):
    label: str
    blur_score: float
    brightness: float
    contrast: float
    issues: list[str]
    width: int
    height: int
    acceptable_for_analysis: bool
    skin_fraction: float | None = None
    hair_fraction: float | None = None
    occlusion_fraction: float | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    action: str
    resource: str | None
    detail: str | None
    ip_address: str | None
    created_at: datetime


class DashboardStats(BaseModel):
    total_cases: int
    total_images: int
    breakdowns: dict[str, dict[str, int]]   # only the breakdowns the caller's role may see


class PatientBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    age: int | None = None
    gender: str | None = None
    medical_history: str | None = None
    known_allergies: str | None = None


# ---- role-shaped responses: every field except the ids is optional and left empty when hidden ----
class ImageView(BaseModel):
    id: int
    case_id: int
    original_filename: str | None = None
    image_source: str | None = None
    capture_date: date | None = None
    body_location: str | None = None
    file_format: str | None = None
    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    quality_label: str | None = None
    blur_score: float | None = None
    brightness: float | None = None
    contrast: float | None = None
    quality_issues: list[str] | None = None
    analysis_status: str | None = None
    model_version: str | None = None
    prediction_result: dict | None = None
    lesion_info: dict | None = None
    created_at: datetime | None = None


class HistoryView(ImageView):
    case_code: str
    owner_name: str | None = None


class CasePermissions(BaseModel):
    edit: bool = False
    delete: bool = False
    upload: bool = False
    add_notes: bool = False


class CaseView(BaseModel):
    id: int
    case_code: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_name: str | None = None
    patient_age: int | None = None
    patient_gender: str | None = None
    medical_history: str | None = None
    known_allergies: str | None = None
    clinical_notes: str | None = None
    body_location: str | None = None
    images: list[ImageView] = []
    notes: list[NoteOut] = []
    permissions: CasePermissions = CasePermissions()


class CaseSummaryView(BaseModel):
    id: int
    case_code: str
    created_at: datetime | None = None
    owner_name: str | None = None
    body_location: str | None = None
    patient_age: int | None = None
    patient_gender: str | None = None
    image_count: int = 0
    latest_quality: str | None = None
    latest_status: str | None = None


class NotificationOut(BaseModel):
    key: str
    level: Literal["informational", "low", "medium", "high"]
    title: str
    message: str
    case_id: int
    case_code: str
    image_id: int | None = None
    created_at: datetime | None = None
    read: bool = False


class NotificationKeys(BaseModel):
    keys: list[Annotated[str, StringConstraints(max_length=64)]] = Field(max_length=200)

