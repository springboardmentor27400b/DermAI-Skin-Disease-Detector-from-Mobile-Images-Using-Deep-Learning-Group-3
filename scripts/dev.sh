#!/usr/bin/env bash
# Runs backend (8000) and frontend (5173) for local development.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements.txt
[ -f backend/.env ] || cp backend/.env.example backend/.env
(cd frontend && npm install --silent)
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
wait

