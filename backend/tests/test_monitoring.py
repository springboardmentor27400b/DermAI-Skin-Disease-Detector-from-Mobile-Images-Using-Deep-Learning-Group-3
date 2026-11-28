"""Monitoring and logging: readiness probe and the administrator metrics endpoint."""
from tests.conftest import register_and_login


def _admin(client):
    r = client.post("/api/auth/login", data={"username": "admin@dermai.local", "password": "ChangeMe!2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_readiness_reports_database_storage_and_model(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["checks"]["database"] == "ok" and body["checks"]["storage"] == "ok" and "model" in body["checks"]


def test_metrics_are_admin_only_and_count_requests(client):
    ph = register_and_login(client, "mon-pat@example.com")
    assert client.get("/api/metrics", headers=ph).status_code == 403
    client.get("/api/health"); client.get("/api/cases", headers=ph)
    m = client.get("/api/metrics", headers=_admin(client)).json()
    assert m["requests_total"] >= 2 and "2xx" in m["by_status"] and m["uptime_seconds"] >= 0
    assert any(k.startswith("GET /api/cases") for k in m["routes"])          # grouped by route template
    assert {"users", "cases", "images", "analysis_status", "failed_logins_total", "active_model"} <= set(m)
