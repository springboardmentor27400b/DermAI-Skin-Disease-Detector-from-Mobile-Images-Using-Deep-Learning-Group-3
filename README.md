# DermAI: Skin Disease Detector from Mobile Images Using Deep Learning

Milestone 1 (Weeks 1-2): project initialisation, dataset selection, and core platform.
DermAI is an AI-assisted screening and research tool. It is **not** a medical diagnosis system.

## What is in this milestone
- **Backend** (FastAPI, SQLAlchemy): JWT auth, role-based access, case management, image upload, quality assessment, preprocessing, audit log.
- **Frontend** (React, TypeScript, Tailwind): swipeable role entry (patient, clinician, researcher) with role-specific sign-up and themes, dashboard, cases, camera or gallery capture with a quality check, notes, history and comparison, profile, admin (including clinician verification).
- **ML tooling**: PAD-UFES-20 class definitions, EDA with real results, patient-grouped 5-fold and train/val/test splits.
- **Docs**: architecture, schema, dataset decision, wireframes, checklist.

## Quick start (no Node.js needed)
```bash
pip install -r requirements.txt
cd backend && cp .env.example .env     # Windows: copy .env.example .env
uvicorn app.main:app --port 8000
```
Open http://localhost:8000 for the public home page (Sign in / Get started lead to the role entry). The pre-built web app is in `backend/frontend_dist`. Node.js is only needed to edit the UI.

## Quick start (development, with Node.js)
```bash
./scripts/dev.sh            # backend :8000 (docs at /docs), frontend :5173
```
or with Docker:
```bash
docker compose up --build   # app at http://localhost:8080, API at :8000/docs
```
Default admin: `admin@dermai.local` / `ChangeMe!2026` (override with env vars; change it).

Run the tests:
```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest -q
cd ../frontend && npm install && npm run build
```

## Roles
Patient, Dermatologist / Clinician, Medical Researcher, Data Scientist / ML Engineer and Administrator each see different case data and have different actions. See `docs/role_permissions.md`. Patients opt in to research use of their de-identified cases; researchers and ML engineers only see opted-in cases.

## Pages
| Route | Page |
|---|---|
| `/` | Public home page (About, How it works, Conditions, Tips) |
| `/welcome` | Role entry: swipeable sign-in / sign-up for patient, clinician, researcher |
| `/dashboard` | Signed-in dashboard (left sidebar layout) |
| `/cases`, `/cases/new`, `/cases/:id` | Case management |
| `/history` | Prediction history and comparison |
| `/profile` | Profile details, edit, change password |
| `/admin` | Administration (admin only) |

## Layout
```
backend/   FastAPI app, preprocessing engine, tests
frontend/  React web app
ml/        dataset classes, EDA, split scripts
docs/      architecture, database schema, dataset selection, wireframes, checklist
```

## Milestone 2 (Weeks 3-4)
Lesion detection and ROI preprocessing, a classifier service in the API (top-3 predictions, calibrated confidence, caveats, re-analysis), and the ML training and model-comparison toolkit in `ml/`. See `docs/milestone2_checklist.md` for what is done and the commands to train the first real models. The API runs without a model (uploads stay `pending`); deploy one with `ml/export_model.py`, and install `backend/requirements-inference.txt` for torch.

## Milestone 3 (Weeks 5-6)
Swin / ViT / ConvNeXt-Small / EfficientNetV2 in the model zoo, post-hoc and deployable ensembles, Grad-CAM attention maps on the deployed model, data-fitted risk categories, the medical image analysis screen (`/analysis/:id`), notifications and an admin model registry. See `docs/milestone3_checklist.md` (what is done, what still needs your GPU runs, and the commands) and `docs/risk_protocol.md`.

## Milestone 4 (Weeks 7-8)
Security hardening (login lockout, headers, production guard), monitoring (`/api/health/ready`, admin `/api/metrics`, request-ID logs), end-to-end and security tests, Docker healthchecks, CI, deployment guide. See `docs/milestone4_checklist.md` and `docs/DEPLOY_STEP_BY_STEP.md`.

## Still outstanding

Reporting polish, end-to-end and security testing, Docker and cloud deployment, monitoring, user guide and final presentation. The React Native app is still outstanding.

Note: the home page imports `frontend/src/assets/hero-dermai.webp`; add your own image there before `npm run build` (it is not included in this source package).

