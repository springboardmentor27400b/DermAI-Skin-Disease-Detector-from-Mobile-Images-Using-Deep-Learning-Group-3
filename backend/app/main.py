import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.routes import admin, auth, cases, images, models, notifications, patients, reports
from app.core.config import settings
from app.core.observability import ObservabilityMiddleware, metrics, setup_logging
from app.core.security import hash_password
from app.db.migrate import add_missing_columns
from app.db.session import Base, SessionLocal, engine, get_db
from app.inference import classifier
from app.models import AuditLog, Case, ImageRecord, User

setup_logging()
log = logging.getLogger("dermai")


def check_production_settings() -> None:
    """A production deployment must not run on the development defaults."""
    if settings.environment != "production":
        return
    problems = []
    if settings.secret_key == "dev-only-change-me" or len(settings.secret_key) < 32:
        problems.append("SECRET_KEY must be a random string of at least 32 characters (openssl rand -hex 32)")
    if settings.first_admin_password == "ChangeMe!2026":
        problems.append("FIRST_ADMIN_PASSWORD must not be the default")
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


def init_db() -> None:
    check_production_settings()
    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)             # keeps older local databases working; Alembic comes later
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.processed_dir).mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.role == "admin")):
            db.add(
                User(
                    email=settings.first_admin_email.lower(),
                    full_name="DermAI Administrator",
                    hashed_password=hash_password(settings.first_admin_password),
                    role="admin",
                )
            )
            db.commit()
    m = classifier.get_model()
    log.info("DermAI %s started (%s). Model: %s", settings.app_version, settings.environment, m.version if m else "none, uploads stay pending")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-assisted skin image analysis. Research / decision-support only; not a medical diagnosis.",
    lifespan=lifespan,
)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(cases.router)
api.include_router(reports.router)
api.include_router(images.router)
api.include_router(patients.router)
api.include_router(admin.router)
api.include_router(models.router)
api.include_router(notifications.router)


@api.get("/health", tags=["system"])
def health():
    """Liveness: the process is up."""
    return {"status": "ok", "version": settings.app_version}


@api.get("/health/ready", tags=["system"])
def ready(db: Session = Depends(get_db)):
    """Readiness: database reachable, storage writable, model state. Used by the Docker healthcheck and cloud load balancers."""
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1")); checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    checks["storage"] = "ok" if os.access(settings.upload_dir, os.W_OK) and os.access(settings.processed_dir, os.W_OK) else "error"
    m = classifier.get_model()
    checks["model"] = m.version if m else "none (uploads stay pending)"
    good = checks["database"] == "ok" and checks["storage"] == "ok"
    return JSONResponse({"status": "ok" if good else "degraded", "checks": checks}, status_code=200 if good else 503)


@api.get("/metrics", tags=["system"])
def system_metrics(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    """Administrator-only platform health: request counts and latency, usage totals, analysis outcomes, failed logins."""
    by_status = dict(db.execute(select(ImageRecord.analysis_status, func.count()).group_by(ImageRecord.analysis_status)).all())
    by_model = dict(db.execute(select(ImageRecord.model_version, func.count()).where(ImageRecord.model_version.is_not(None)).group_by(ImageRecord.model_version)).all())
    bad_logins = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "auth.login_failed")) or 0
    blocked = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "auth.login_blocked")) or 0
    m = classifier.get_model()
    return {**metrics.snapshot(),
            "users": db.scalar(select(func.count()).select_from(User)), "cases": db.scalar(select(func.count()).select_from(Case)),
            "images": sum(by_status.values()), "analysis_status": by_status, "model_usage": by_model,
            "failed_logins_total": bad_logins, "blocked_logins_total": blocked, "active_model": m.version if m else None}


app.include_router(api)


# Serve the pre-built web app (backend/frontend_dist) so Node.js is not needed just to run DermAI.
# Rebuild it with `npm run build` in frontend/ and copy dist/ here if you change the UI.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend_dist"
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (FRONTEND_DIST / full_path).resolve()
        if full_path and f.is_file() and FRONTEND_DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
