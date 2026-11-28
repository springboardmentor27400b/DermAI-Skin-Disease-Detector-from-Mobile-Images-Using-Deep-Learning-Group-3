# Milestone 1 checklist (Weeks 1-2)

| Task from the brief | Status | Where |
|---|---|---|
| Define project objectives and workflow | Done | README, docs/architecture.md |
| Select target skin conditions | Done (6 PAD-UFES-20 classes: ACK, BCC, MEL, NEV, SCC, SEK) | docs/dataset_selection.md, ml/datasets.py |
| Select public / de-identified dataset | Done (PAD-UFES-20, smartphone images) | docs/dataset_selection.md |
| Understand dataset structure and annotations | Done (documented) | docs/dataset_selection.md |
| Exploratory data analysis | Done. Metadata and image integrity checked on your machine: 2,298 images, none missing, unlisted, unreadable or duplicated | ml/eda.py, ml/reports/eda/ |
| Analyze class distribution | Done: 16.2:1 imbalance, class weights suggested | ml/reports/eda_pad_ufes_20/summary.json |
| Design system architecture | Done | docs/architecture.md |
| Design database schema | Done | docs/database_schema.md, backend/app/models |
| Create UI wireframes | Done | docs/wireframes.md |
| Set up frontend and backend | Done | frontend/, backend/ |
| Implement authentication (JWT, RBAC, audit) | Done, tested | backend/app/api/routes/auth.py |
| Implement case management | Done, tested | backend/app/api/routes/cases.py |
| Implement image upload | Done, tested | backend/app/api/routes/images.py |
| Initial preprocessing pipeline | Done, tested | backend/app/preprocessing |

## Added after review
| Feature | Where |
|---|---|
| Role-based entry: swipeable Patient / Clinician / Researcher sign-in and sign-up with role-specific fields and themes | frontend/src/pages/AuthPage.tsx |
| Clinician verification by admin before cross-user case access | backend/app/api/deps.py, routes/admin.py |
| Case management: notes timeline, prediction history with filters, side-by-side comparison, all case and image fields | CaseDetail, History, Compare, Notes |
| Public home page, left sidebar layout, profile page listing user details with edit and password change | frontend/src/pages/Home.tsx, components/Layout.tsx, pages/Profile.tsx |

| Five-role permission matrix (field visibility and actions), clinician on-behalf case creation, research consent | docs/role_permissions.md, backend/app/core/permissions.py |

## Verification performed
- Backend: 39 pytest tests pass and 1 is skipped (it needs PyTorch, which is optional). They cover auth, RBAC, clinician verification, case isolation, notes, history, upload, validation, preprocessing, the database upgrade, lesion detection and the analysis pipeline.
- Browser run (Chromium): sign-up for each role, prefill, upload, compare, notes, wrong-portal guard, admin verification, mobile swipe.
- Frontend: `tsc` type-check and production build pass. Hover effects are in place and respect touch devices and the reduced-motion setting.
- Image dataset: `eda.py --verify-images` on your machine found 2,298 files, none missing, unlisted, unreadable or duplicated.
- Quality thresholds: after switching to the data-based cut-offs, `quality_audit.py` on all 2,298 photos rates 61.6% good, 29.9% acceptable and 8.5% poor (it was 17.0 / 47.3 / 35.7 with the original cut-offs).
- ML scripts: the earlier outputs in `ml/reports/eda_pad_ufes_20/` and `ml/data/splits/` come from the real PAD-UFES-20 metadata. The current scripts replace the earlier ones and were tested on synthetic data shaped like PAD-UFES-20 (including missing, unlisted and corrupt image files, and both column-naming styles); the grouped split asserts zero patient overlap. They have not yet been run on your real images.

## Still to do
1. Look at the contact sheets from `ml/quality_review.py` (see `docs/quality_thresholds.md`) to confirm the lowest-scoring photos really are unusable. The audit numbers are done; this by-eye check is not recorded yet.
2. Decide how to handle the 15 images with a shorter side under 224 px (upscale or exclude in training). The web app also rejects uploads under 224 px.
3. Decide which splits to keep. The earlier `ml/data/splits/` files came from the previous script. The current script refuses to overwrite them unless you pass `--force`.
4. Collect evidence for the Week 2 review: EDA charts, `summary.json`, `split_report.json`, the quality audit results, and screenshots of the running app.
5. Change `SECRET_KEY` and the admin password before any shared deployment.

