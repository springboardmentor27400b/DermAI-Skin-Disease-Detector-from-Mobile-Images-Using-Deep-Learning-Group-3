from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DermAI API"
    app_version: str = "0.4.0"

    # "production" refuses to start with the development secret key or the default admin password.
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./dermai.db"

    secret_key: str = "dev-only-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Failed-login lockout (per client IP + email)
    login_max_failures: int = 5
    login_lock_seconds: int = 300

    upload_dir: str = "./storage/uploads"
    processed_dir: str = "./storage/processed"
    max_upload_mb: int = 10
    min_resolution: int = 224          # shorter side, pixels
    model_input_size: int = 224
    roi_size: int = 256                # lesion-ROI crop stored / fed to the classifier pipeline (model sees model_input_size)
    allowed_formats: list[str] = ["JPEG", "PNG"]

    # Researchers / ML engineers only see cases from patients who opted in to research use.
    research_requires_consent: bool = True

    # Image-quality cut-offs. Provisional: blur and contrast come from the 5th (poor) and 25th (acceptable)
    # percentiles of PAD-UFES-20 (docs/quality_thresholds.md). Previous defaults were blur 40/100, contrast 15/28.
    quality_blur_poor: float = 13.0           # variance of the Laplacian on a 512 px grayscale copy
    quality_blur_acceptable: float = 33.0
    quality_contrast_poor: float = 13.0       # standard deviation of grey levels
    quality_contrast_acceptable: float = 18.0
    quality_dark_poor: float = 35.0           # mean grey level 0-255
    quality_dark_acceptable: float = 60.0
    quality_bright_acceptable: float = 205.0
    quality_bright_poor: float = 225.0

    # Inference (Milestone 2). Models live in <model_dir>/<version>/{model.ts.pt, meta.json}; <model_dir>/active.json picks one.
    model_dir: str = "./models"
    active_model: str | None = None            # env override of active.json
    inference_threads: int = 2
    # Provisional: flags predictions whose calibrated top probability is below this. Re-set it from validation data.
    low_confidence_threshold: float = 0.5

    # Explainability (Milestone 3): gradcam | gradcampp. Needs features.ts.pt + head.ts.pt next to the model (ml/export_model.py).
    explain_method: str = "gradcam"
    explain_overlay_alpha: float = 0.45

    # Informational image checks (never reject a photo on their own; provisional, check with ml/quality_audit.py)
    quality_skin_fraction_low: float = 0.5
    quality_hair_fraction_high: float = 0.06
    quality_occlusion_fraction: float = 0.12

    cors_origins: list[str] = ["http://localhost:5173"]

    first_admin_email: str = "admin@dermai.local"
    first_admin_password: str = "ChangeMe!2026"


settings = Settings()
