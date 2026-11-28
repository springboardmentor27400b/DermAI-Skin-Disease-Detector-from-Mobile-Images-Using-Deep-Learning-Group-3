import enum


class Role(str, enum.Enum):
    patient = "patient"
    dermatologist = "dermatologist"
    researcher = "researcher"
    ml_engineer = "ml_engineer"
    admin = "admin"


# Roles that may self-register. ML engineers and admins are provisioned by an admin;
# dermatologists may sign up but need admin verification before gaining clinician access.
SELF_REGISTER_ROLES = {Role.patient.value, Role.dermatologist.value, Role.researcher.value}


class AnalysisStatus(str, enum.Enum):
    pending = "pending"                  # preprocessed, awaiting model (Milestone 2)
    rejected_quality = "rejected_quality"
    completed = "completed"
    failed = "failed"


class ImageSource(str, enum.Enum):
    camera = "camera"
    gallery = "gallery"
    dataset = "dataset"


class QualityLabel(str, enum.Enum):
    good = "good"
    acceptable = "acceptable"
    poor = "poor"

