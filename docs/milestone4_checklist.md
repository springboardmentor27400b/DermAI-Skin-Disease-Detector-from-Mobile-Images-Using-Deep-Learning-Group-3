# Milestone 4 checklist (Weeks 7-8): reporting, testing, analytics and deployment

Status key: **Done** (in the repo and tested), **Written** (code is here, not yet run by you), **You run** (command exists, needs your machine or data), **Open**.

| Task from the brief | Status | Where |
|---|---|---|
| Complete dashboard | Done in M3 (role dashboards, model card, notifications). Admin platform health: Written | `GET /api/metrics` |
| Automated reports, PDF / CSV / JSON | Done | `services/report.py` |
| Prediction history, notifications | Done | History, Notifications |
| End-to-end testing | Written: `tests/test_end_to_end.py` (patient, clinician, researcher, admin, reports, consent withdrawal, delete) | backend/tests |
| API testing | Done: ~80 tests across auth, permissions, cases, images, reports, M3. Postman collection: Open (optional; `/docs` also works) | backend/tests |
| Image-quality testing | You run: `ml/quality_audit.py` (done, 8.5% poor) and `ml/quality_eval.py` once you hand-label ~150 photos | ml/ |
| Model inference testing | Done: `test_analysis.py`, `test_milestone3.py`. CV results in `ml/reports/final_evaluation.md` | |
| Security testing | Written: `tests/test_security.py` (anonymous sweep, role sweep, forged / expired / `alg=none` tokens, lockout, injection-style input, upload limit, headers, production-secret guard) | backend/tests |
| Performance testing | You run: `python scripts/benchmark.py --base http://localhost:8000/api --image <photo> --n 10 --concurrency 4` with the model deployed; paste the table into the report | scripts/ |
| Dockerize | Written: healthchecks, restart policy, proxy headers, models volume writable, env-driven secrets | docker-compose.yml, backend/Dockerfile |
| Deploy | You run: see `docs/deployment.md` | |
| Monitoring and logging | Written: access log with request IDs, slow-request warnings, `/api/health/ready`, admin `/api/metrics` (audit log already existed) | core/observability.py |
| CI | Written: build, test, Docker smoke test | .github/workflows/ci.yml |
| Final documentation, user guide, presentation | Open: outline in `docs/final_deliverables.md` | |

## Hardening added in this milestone
- Failed-login lockout (5 failures per client IP + email in 5 minutes, then 429 with `Retry-After`), audit-logged as `auth.login_blocked`.
- Security headers on every response (HSTS in production). `ENVIRONMENT=production` refuses the default `SECRET_KEY` and default admin password.
- Real client IP behind nginx / a load balancer (`--proxy-headers`), so audit logs and the limiter are meaningful.
- Fixed: the models volume was mounted read-only, which would have broken Administration > Models > Deploy (it writes `active.json`).

## Known gaps to state honestly in the final report
- The React Native app and OAuth2 / social login (brief module 1 and tech stack) are not built. The web app captures through the browser camera. Say so.
- The JWT lives in `localStorage` (readable by any script injected into the page) and cannot be revoked before expiry. A stricter design uses httpOnly cookies plus a refresh token. List it as a limitation.
- The login limiter is in-memory, so per container. Use Redis for several replicas.
- Uploaded images are stored unencrypted on a volume. In the cloud use encrypted volumes or S3 / Blob with server-side encryption.
- Model results are pooled cross-validation on one dataset (PAD-UFES-20); SCC F1 is about 0.25; skin-tone coverage is narrow. Keep the "not a diagnosis" wording everywhere.
- Alembic migrations are still the small `migrate.py` upgrader.

## Order to work in
1. Merge these files, run `cd backend && pytest -q`, fix anything that fails (I could not run the suite against your repo).
2. `docker compose up --build`; check `http://localhost:8080` and `http://localhost:8000/api/health/ready`.
3. Run the benchmark with the model deployed; run `quality_eval.py` if you labelled photos.
4. Deploy (docs/deployment.md); screenshot the running app and `/api/metrics`.
5. Final report, user guide, slides, demo.
