# Deployment

## Before any shared deployment
1. Copy `.env.example` to `.env`; set `ENVIRONMENT=production`, a random `SECRET_KEY` (`openssl rand -hex 32`), `POSTGRES_PASSWORD`, `FIRST_ADMIN_PASSWORD`, and `CORS_ORIGINS` to your real URL. The API refuses to start in production with the defaults.
2. Put the trained model in `backend/models/<version>/` (with `active.json`). The folder is git-ignored; copy it to the server.
3. Serve over HTTPS (load balancer or a reverse proxy such as Caddy). Medical images must not travel over plain HTTP.

## Option A: one VM with Docker Compose (simplest; AWS EC2 or Azure VM)
- 2 vCPU / 4 GB RAM is enough for CPU inference of ConvNeXt-Tiny. Open ports 80/443 only; do not expose 8000 or the database.
```bash
git clone <your repo> && cd dermai && cp .env.example .env   # edit it
docker compose up -d --build
curl -fs http://localhost:8080/api/health/ready
```
- Back up the `pgdata` and `media` volumes. Update with `git pull && docker compose up -d --build`.

## Option B: managed containers
- **AWS:** images to ECR; ECS Fargate (or App Runner) behind an Application Load Balancer with an ACM certificate; RDS PostgreSQL; S3 for images (needs a storage adapter in `services/storage.py`, which writes to local disk today); CloudWatch logs. Health check path `/api/health/ready`.
- **Azure:** Azure Container Registry; Container Apps; Azure Database for PostgreSQL; Blob Storage for images (same adapter note); Log Analytics.
- With more than one API replica, local `media` storage and the in-memory login limiter stop working: move images to object storage and the limiter to Redis first.

## Monitoring
- Logs: `docker compose logs -f backend`. One line per request: method, path, status, time, request ID (also returned as `X-Request-ID`). Requests over 2 s and all 5xx are warnings.
- Probes: `/api/health` (alive), `/api/health/ready` (database, storage, model; 503 when degraded).
- Administrator metrics: `GET /api/metrics` (counts by status, slowest routes, users, cases, analysis outcomes, model usage, failed and blocked logins).
- Audit trail: Administration > Audit log.
