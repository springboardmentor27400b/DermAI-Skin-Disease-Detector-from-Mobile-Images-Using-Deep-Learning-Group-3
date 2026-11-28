from tests.conftest import register_and_login


def test_register_login_me(client):
    h = register_and_login(client, "a@example.com")
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200 and r.json()["role"] == "patient"


def test_duplicate_and_weak_password(client):
    register_and_login(client, "dup@example.com")
    r = client.post("/api/auth/register", json={"email": "dup@example.com", "full_name": "Dup", "password": "Passw0rdX"})
    assert r.status_code == 409
    r = client.post("/api/auth/register", json={"email": "weak@example.com", "full_name": "Weak", "password": "alllowercase1"})
    assert r.status_code == 422


def test_cannot_self_register_as_admin(client):
    r = client.post("/api/auth/register", json={"email": "x@example.com", "full_name": "Xx", "password": "Passw0rdX", "role": "admin"})
    assert r.status_code == 422


def test_bad_login_and_unauthenticated(client):
    assert client.post("/api/auth/login", data={"username": "nobody@example.com", "password": "nope"}).status_code == 401
    assert client.get("/api/cases").status_code == 401


def test_admin_only_routes(client):
    h = register_and_login(client, "plain@example.com")
    assert client.get("/api/admin/audit-logs", headers=h).status_code == 403
    r = client.post("/api/auth/login", data={"username": "admin@dermai.local", "password": "ChangeMe!2026"})
    assert r.status_code == 200
    ah = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/admin/audit-logs", headers=ah).status_code == 200
    r = client.post("/api/admin/users", headers=ah, json={"email": "derm@example.com", "full_name": "Dr Derm", "password": "Passw0rdX", "role": "dermatologist"})
    assert r.status_code == 201

