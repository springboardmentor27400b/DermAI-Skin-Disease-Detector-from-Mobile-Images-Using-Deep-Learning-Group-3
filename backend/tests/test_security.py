"""Security testing (brief section 19): authentication, authorisation sweep, token tampering, lockout, upload limits, headers."""
import time

import jwt
import pytest

from app.core.config import settings
from app.services.storage import safe_filename
from tests.conftest import register_and_login

PROTECTED_GETS = ["/api/auth/me", "/api/cases", "/api/cases/stats", "/api/images/history", "/api/images/quality-thresholds",
                  "/api/notifications", "/api/models/active", "/api/models/versions", "/api/admin/users", "/api/admin/audit-logs",
                  "/api/patients", "/api/metrics"]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_every_protected_route_rejects_anonymous_requests(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/api/admin/users", "/api/admin/audit-logs", "/api/models/versions", "/api/metrics", "/api/patients"])
def test_patient_cannot_reach_staff_routes(client, path):
    h = register_and_login(client, "sec-pat@example.com")
    assert client.get(path, headers=h).status_code == 403


def test_tampered_expired_and_unsigned_tokens_are_rejected(client):
    h = register_and_login(client, "sec-tok@example.com")
    good = h["Authorization"].split()[1]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {good[:-3]}abc"}).status_code == 401      # broken signature
    expired = jwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) - 10}, settings.secret_key, algorithm=settings.algorithm)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    wrong_key = jwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) + 600}, "not-the-secret-key-not-the-secret-key", algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {wrong_key}"}).status_code == 401
    unsigned = jwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) + 600}, None, algorithm="none")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401           # alg=none attack


def test_role_claim_in_the_token_does_not_grant_access(client):
    """Authorisation uses the stored role, not the token's claim."""
    me = register_and_login(client, "sec-claim@example.com")
    uid = client.get("/api/auth/me", headers=me).json()["id"]
    forged = jwt.encode({"sub": str(uid), "role": "admin", "exp": int(time.time()) + 600}, settings.secret_key, algorithm=settings.algorithm)
    assert client.get("/api/admin/users", headers={"Authorization": f"Bearer {forged}"}).status_code == 403


def test_login_lockout_after_repeated_failures(client):
    register_and_login(client, "sec-lock@example.com")
    for _ in range(settings.login_max_failures):
        assert client.post("/api/auth/login", data={"username": "sec-lock@example.com", "password": "wrong-Pass1"}).status_code == 401
    r = client.post("/api/auth/login", data={"username": "sec-lock@example.com", "password": "wrong-Pass1"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert client.post("/api/auth/login", data={"username": "sec-lock@example.com", "password": "Passw0rdX"}).status_code == 429   # even the right password
    assert client.post("/api/auth/login", data={"username": "someone-else@example.com", "password": "x"}).status_code == 401       # other accounts unaffected
    tok = client.post("/api/auth/login", data={"username": "admin@dermai.local", "password": "ChangeMe!2026"}).json()["access_token"]
    logs = client.get("/api/admin/audit-logs?limit=500", headers={"Authorization": f"Bearer {tok}"}).json()
    assert any(l["action"] == "auth.login_blocked" for l in logs)


def test_injection_style_login_input_is_just_a_failed_login(client):
    for u in ("' OR 1=1 --", "admin@dermai.local' --", "<script>alert(1)</script>"):
        assert client.post("/api/auth/login", data={"username": u, "password": "x"}).status_code == 401


def test_oversized_upload_is_refused(client):
    h = register_and_login(client, "sec-big@example.com")
    big = b"\0" * (settings.max_upload_mb * 1024 * 1024 + 1)
    assert client.post("/api/images/check-quality", headers=h, files={"file": ("big.jpg", big, "image/jpeg")}).status_code == 413


def test_filenames_cannot_escape_the_storage_folder():
    for name in ("../../etc/passwd", "..\\..\\win.ini", "a/b/c.jpg", "", "x;rm -rf.jpg"):
        s = safe_filename(name)
        assert s and "/" not in s and "\\" not in s
        assert all(c.isalnum() or c in "._-" for c in s)


def test_security_headers_and_request_id(client):
    r = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Request-ID"] == "abc123" and r.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in r.headers          # only in production


def test_production_refuses_default_secrets(monkeypatch):
    from app.main import check_production_settings
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(RuntimeError):
        check_production_settings()
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    monkeypatch.setattr(settings, "first_admin_password", "A-Real-Password-9")
    check_production_settings()
