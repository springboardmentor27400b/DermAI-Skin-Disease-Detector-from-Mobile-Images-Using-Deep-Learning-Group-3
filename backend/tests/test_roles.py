from sqlalchemy import create_engine, text

from app.db.migrate import add_missing_columns
from tests.conftest import make_image


def _signup(client, payload):
    return client.post("/api/auth/register", json=payload)


def _login(client, email, password="Passw0rdX"):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client):
    return _login(client, "admin@dermai.local", "ChangeMe!2026")


def test_patient_signup_stores_health_profile(client):
    r = _signup(client, {"email": "p1@example.com", "full_name": "Pat One", "password": "Passw0rdX", "role": "patient",
                         "age": 34, "gender": "female", "medical_history": "eczema", "known_allergies": "latex",
                         "institution": "ignored"})
    assert r.status_code == 201
    u = r.json()
    assert (u["age"], u["gender"], u["known_allergies"]) == (34, "female", "latex")
    assert u["institution"] is None and u["is_verified"] is True        # irrelevant fields dropped


def test_clinician_signup_requires_credentials_and_starts_unverified(client):
    base = {"email": "d1@example.com", "full_name": "Dr One", "password": "Passw0rdX", "role": "dermatologist"}
    assert _signup(client, base).status_code == 422
    r = _signup(client, {**base, "institution": "City Hospital", "license_number": "KMC-12345", "specialization": "Dermatology"})
    assert r.status_code == 201 and r.json()["is_verified"] is False


def test_researcher_requires_institution_and_validates_orcid(client):
    base = {"email": "r1@example.com", "full_name": "Res One", "password": "Passw0rdX", "role": "researcher"}
    assert _signup(client, base).status_code == 422
    assert _signup(client, {**base, "institution": "Univ", "orcid": "bad"}).status_code == 422
    r = _signup(client, {**base, "institution": "Univ", "research_area": "Melanoma AI", "orcid": "0000-0002-1825-0097"})
    assert r.status_code == 201 and r.json()["orcid"] == "0000-0002-1825-0097"


def test_unverified_clinician_cannot_see_others_until_verified(client):
    _signup(client, {"email": "pat2@example.com", "full_name": "Pat Two", "password": "Passw0rdX", "role": "patient"})
    ph = _login(client, "pat2@example.com")
    case = client.post("/api/cases", headers=ph, json={"patient_age": 50}).json()

    r = _signup(client, {"email": "d2@example.com", "full_name": "Dr Two", "password": "Passw0rdX", "role": "dermatologist",
                         "institution": "Clinic", "license_number": "L-1"})
    dh = _login(client, "d2@example.com")
    assert client.get(f"/api/cases/{case['id']}", headers=dh).status_code == 404

    ah = _admin(client)
    assert client.patch(f"/api/admin/users/{r.json()['id']}/verify?verified=true", headers=ah).status_code == 200
    got = client.get(f"/api/cases/{case['id']}", headers=dh)
    assert got.status_code == 200 and got.json()["owner_name"] == "Pat Two"

    # changing the licence number drops verification again
    client.patch("/api/auth/me", headers=dh, json={"license_number": "L-2"})
    assert client.get(f"/api/cases/{case['id']}", headers=dh).status_code == 404


def test_only_admin_can_verify_and_only_clinicians(client):
    ph = _login(client, "pat2@example.com")
    assert client.patch("/api/admin/users/1/verify?verified=true", headers=ph).status_code == 403
    assert client.patch(f"/api/admin/users/{client.get('/api/auth/me', headers=ph).json()['id']}/verify?verified=true", headers=_admin(client)).status_code == 400


def test_notes_are_clinician_only_and_carry_author(client):
    _signup(client, {"email": "pat3@example.com", "full_name": "Pat Three", "password": "Passw0rdX"})
    ph = _login(client, "pat3@example.com")
    case = client.post("/api/cases", headers=ph, json={}).json()
    assert client.post(f"/api/cases/{case['id']}/notes", headers=ph, json={"text": "Itchy"}).status_code == 403   # patients add no notes

    ah = _admin(client)
    r = client.post("/api/admin/users", headers=ah, json={"email": "dn@example.com", "full_name": "Dr Note", "password": "Passw0rdX", "role": "dermatologist"})
    assert r.status_code == 201
    dh = _login(client, "dn@example.com")
    assert client.post(f"/api/cases/{case['id']}/notes", headers=dh, json={"text": "   "}).status_code == 422
    n = client.post(f"/api/cases/{case['id']}/notes", headers=dh, json={"text": "Review in 2 weeks"})
    assert n.status_code == 201 and n.json()["author_name"] == "Dr Note" and n.json()["author_role"] == "dermatologist"
    assert len(client.get(f"/api/cases/{case['id']}", headers=dh).json()["notes"]) == 1
    assert client.get(f"/api/cases/{case['id']}", headers=ph).json()["notes"] == []     # patient never receives notes


def test_history_filters_and_isolation(client):
    _signup(client, {"email": "pat4@example.com", "full_name": "Pat Four", "password": "Passw0rdX"})
    h = _login(client, "pat4@example.com")
    case = client.post("/api/cases", headers=h, json={"body_location": "arm"}).json()
    for d in ("2026-01-05", "2026-03-10"):
        r = client.post(f"/api/cases/{case['id']}/images", headers=h, files={"file": ("a.jpg", make_image("good"), "image/jpeg")},
                        data={"capture_date": d, "image_source": "camera"})
        assert r.status_code == 201
    allh = client.get("/api/images/history", headers=h).json()
    assert len(allh) == 2 and allh[0]["case_code"] == case["case_code"] and allh[0]["prediction_result"] is None
    assert len(client.get("/api/images/history?date_from=2026-02-01", headers=h).json()) == 1
    assert client.get("/api/images/history?analysis_status=completed", headers=h).json() == []
    other = _login(client, "pat3@example.com")
    assert all(i["case_id"] != case["id"] for i in client.get("/api/images/history", headers=other).json())


def test_old_database_is_upgraded(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), full_name VARCHAR(120), "
                       "hashed_password VARCHAR(255), role VARCHAR(32), is_active BOOLEAN, created_at DATETIME)"))
        c.execute(text("INSERT INTO users (email, full_name, hashed_password, role, is_active) VALUES ('a@b.co','A','x','patient',1)"))
    added = add_missing_columns(eng)
    assert "users.is_verified" in added and "users.license_number" in added
    with eng.begin() as c:
        assert c.execute(text("SELECT is_verified FROM users")).scalar() == 1     # existing users stay verified

