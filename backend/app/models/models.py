from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="patient", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Clinicians must be verified by an admin before they can see other users' cases.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Role-specific profile (see app/schemas ROLE_FIELDS)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    institution: Mapped[str | None] = mapped_column(String(160), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    research_area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    orcid: Mapped[str | None] = mapped_column(String(19), nullable=True)
    # Patients: allow de-identified cases to be used by researchers / ML engineers.
    research_consent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    cases: Mapped[list["Case"]] = relationship(back_populates="owner", foreign_keys="Case.owner_id")


class Case(Base):
    """A skin-image analysis case. Use de-identified data only (see docs/dataset_selection.md)."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # clinician who opened it for a patient

    patient_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_location: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    owner: Mapped[User] = relationship(back_populates="cases", foreign_keys=[owner_id])
    images: Mapped[list["ImageRecord"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="ImageRecord.id"
    )
    notes: Mapped[list["CaseNote"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="CaseNote.id"
    )

    @property
    def owner_name(self) -> str:
        return self.owner.full_name


class ImageRecord(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(512))
    processed_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    lesion_path: Mapped[str | None] = mapped_column(String(512), nullable=True)      # overlay with lesion outline
    cam_path: Mapped[str | None] = mapped_column(String(512), nullable=True)         # Grad-CAM attention overlay (Milestone 3)
    saliency_path: Mapped[str | None] = mapped_column(String(512), nullable=True)    # gradient saliency map

    image_source: Mapped[str] = mapped_column(String(16), default="gallery")
    capture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    body_location: Mapped[str | None] = mapped_column(String(64), nullable=True)

    file_format: Mapped[str] = mapped_column(String(8))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)

    # Image quality assessment (heuristic in M1, calibrated in M2)
    quality_label: Mapped[str] = mapped_column(String(16))
    blur_score: Mapped[float] = mapped_column(Float)
    brightness: Mapped[float] = mapped_column(Float)
    contrast: Mapped[float] = mapped_column(Float)
    quality_issues: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list

    lesion_info: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON from preprocessing.lesion

    # Filled in by the classifier (Milestone 2)
    analysis_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prediction_result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    case: Mapped[Case] = relationship(back_populates="images")

    @property
    def case_code(self) -> str:
        return self.case.case_code

    @property
    def owner_name(self) -> str:
        return self.case.owner.full_name


class CaseNote(Base):
    """Timeline entry on a case (patient remark or clinical note)."""

    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    case: Mapped[Case] = relationship(back_populates="notes")
    author: Mapped[User] = relationship()

    @property
    def author_name(self) -> str:
        return self.author.full_name

    @property
    def author_role(self) -> str:
        return self.author.role


class RevokedToken(Base):
    """JWTs invalidated at sign-out. Rows can be deleted once expires_at has passed."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotificationRead(Base):
    """Notifications a user has marked as read (alerts themselves are derived, see api/routes/notifications.py)."""

    __tablename__ = "notification_reads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

