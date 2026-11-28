"""Role permission matrix (docs/role_permissions.md), checked through the real API."""
from tests.conftest import make_image

PW = "Passw0rdX"


def _login(client, email, password=PW):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client):
    return _login(client, "admin@dermai.local", "ChangeMe!2026")


def _patient(client, email, consent=False):
    r = client.post("/api/auth/register", json={"email": email, "full_name": f"P {email[:4]}", "password": PW, "role": "patient",
                                                "age": 40, "gender": "male", "medical_history": "asthma", "research_consent": consent})
    assert r.status_code == 201, r.text
    return _login(client, email)


def _staff(client, email, role):
    r = client.post("/api/admin/users", headers=_admin(client), json={"email": email, "full_name": f"S {email[:4]}", "password": PW, "role": role})
    assert r.status_code == 201, r.text
    return _login(client, email)


def _case_with_image(client, h, **case):
    c = client.post("/api/cases", headers=h, json={"body_location": "arm", "patient_age": 40, "medical_history": "asthma", **case}).json()
    r = client.post(f"/api/cases/{c['id']}/images", headers=h, files={"file": ("secret_name.jpg", make_image("good"), "image/jpeg")},
                    data={"capture_date": "2026-05-01", "image_source": "camera"})
    assert r.status_code == 201, r.text
    return c["id"], r.json()["id"]


def test_patient_sees_no_technical_data_and_cannot_write_clinical_notes(client):
    h = _patient(client, "mx1@example.com")
    c = client.post("/api/cases", headers=h, json={"patient_age": 30, "clinical_notes": "I am a doctor now"}).json()
    assert c["clinical_notes"] is None                                   # silently dropped for patients
    cid, iid = _case_with_image(client, h)
    img = client.get(f"/api/cases/{cid}", headers=h).json()["images"][0]
    for hidden in ("model_version", "image_source", "original_filename", "width", "blur_score"):
        assert img[hidden] is None, hidden
    for shown in ("capture_date", "body_location", "analysis_status", "quality_label"):
        assert img[shown] is not None, shown
    assert client.post(f"/api/cases/{cid}/notes", headers=h, json={"text": "x"}).status_code == 403


def test_clinician_sees_everything_and_can_open_case_for_patient(client):
    ph = _patient(client, "mx2@example.com")
    me = client.get("/api/auth/me", headers=ph).json()
    dh = _staff(client, "dc1@example.com", "dermatologist")
    pts = client.get("/api/patients?q=mx2", headers=dh).json()
    assert pts and pts[0]["id"] == me["id"] and pts[0]["medical_history"] == "asthma"

    case = client.post("/api/cases", headers=dh, json={"patient_id": me["id"], "body_location": "leg"})
    assert case.status_code == 201, case.text
    cid = case.json()["id"]
    r = client.post(f"/api/cases/{cid}/images", headers=dh, files={"file": ("a.jpg", make_image("good"), "image/jpeg")})
    assert r.status_code == 201
    full = client.get(f"/api/cases/{cid}", headers=dh).json()
    assert full["owner_name"] == f"P {'mx2@'}" and full["permissions"]["add_notes"] and full["permissions"]["upload"]
    img = full["images"][0]
    assert img["image_source"] and img["width"] and img["original_filename"] and "model_version" in img
    assert client.get(f"/api/cases/{cid}", headers=ph).status_code == 200      # patient owns it


def test_on_behalf_rules(client):
    ph = _patient(client, "mx3@example.com"); other = _patient(client, "mx4@example.com")
    oid = client.get("/api/auth/me", headers=other).json()["id"]
    assert client.post("/api/cases", headers=ph, json={"patient_id": oid}).status_code == 403     # patients act only for themselves
    assert client.get("/api/patients", headers=ph).status_code == 403
    client.post("/api/auth/register", json={"email": "unv@example.com", "full_name": "Dr Unv", "password": PW, "role": "dermatologist",
                                           "institution": "X", "license_number": "L1"})
    uh = _login(client, "unv@example.com")
    assert client.post("/api/cases", headers=uh, json={"patient_id": oid}).status_code == 403     # unverified clinician
    assert client.get("/api/patients", headers=uh).status_code == 403


def test_researcher_is_read_only_deidentified_and_consent_gated(client):
    shared = _patient(client, "rs1@example.com", consent=True)
    private = _patient(client, "rs2@example.com", consent=False)
    sid, siid = _case_with_image(client, shared)
    pid, _ = _case_with_image(client, private)
    rh = _staff(client, "res1@example.com", "researcher")

    assert client.post("/api/cases", headers=rh, json={}).status_code == 403
    assert client.post(f"/api/cases/{sid}/images", headers=rh, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).status_code == 403
    assert client.post(f"/api/cases/{sid}/notes", headers=rh, json={"text": "x"}).status_code == 403
    assert client.delete(f"/api/cases/{sid}", headers=rh).status_code == 403

    assert client.get(f"/api/cases/{pid}", headers=rh).status_code == 404                 # no consent -> not visible
    d = client.get(f"/api/cases/{sid}", headers=rh).json()
    for hidden in ("owner_name", "patient_age", "patient_gender", "medical_history", "known_allergies", "clinical_notes"):
        assert d[hidden] is None, hidden
    assert d["body_location"] == "arm" and d["notes"] == []
    img = d["images"][0]
    assert img["image_source"] == "camera" and img["capture_date"] == "2026-05-01" and "model_version" in img
    assert img["original_filename"] is None                                              # file names can identify people
    assert client.get(f"/api/images/{siid}/file", headers=rh).status_code == 200
    ids = [h["case_id"] for h in client.get("/api/images/history", headers=rh).json()]
    assert sid in ids and pid not in ids
    assert all(h["owner_name"] is None for h in client.get("/api/images/history", headers=rh).json())

    # withdrawing consent removes access immediately
    client.patch("/api/auth/me", headers=shared, json={"research_consent": False})
    assert client.get(f"/api/cases/{sid}", headers=rh).status_code == 404


def test_ml_engineer_sees_technical_fields_only(client):
    ph = _patient(client, "ml1@example.com", consent=True)
    cid, iid = _case_with_image(client, ph)
    mh = _staff(client, "ml-eng@example.com", "ml_engineer")
    d = client.get(f"/api/cases/{cid}", headers=mh).json()
    assert d["case_code"] and d["body_location"] is None and d["patient_age"] is None and d["owner_name"] is None
    img = d["images"][0]
    assert img["image_source"] == "camera" and img["analysis_status"] and "model_version" in img and "prediction_result" in img
    assert img["capture_date"] is None and img["body_location"] is None
    assert client.post("/api/cases", headers=mh, json={}).status_code == 403
    h = client.get("/api/images/history?date_from=2099-01-01", headers=mh).json()        # date filter ignored: cannot probe hidden dates
    assert any(x["case_id"] == cid for x in h)


def test_admin_gets_operational_view_only(client):
    ph = _patient(client, "ad1@example.com")
    cid, iid = _case_with_image(client, ph)
    ah = _admin(client)
    d = client.get(f"/api/cases/{cid}", headers=ah).json()
    assert d["case_code"] and d["owner_name"] is None and d["patient_age"] is None and d["clinical_notes"] is None
    img = d["images"][0]
    assert img["analysis_status"] and img["image_source"] and "model_version" in img
    for hidden in ("capture_date", "body_location", "quality_label", "prediction_result", "original_filename", "width"):
        assert img[hidden] is None, hidden
    assert client.get(f"/api/images/{iid}/file", headers=ah).status_code == 403            # no image files
    assert client.delete(f"/api/cases/{cid}", headers=ah).status_code == 403               # audit only
    assert client.post(f"/api/cases/{cid}/notes", headers=ah, json={"text": "x"}).status_code == 403
    assert client.post("/api/cases", headers=ah, json={}).status_code == 403
    assert client.post("/api/images/check-quality", headers=ah, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).status_code == 403
    s = client.get("/api/cases/stats", headers=ah).json()["breakdowns"]
    assert "users_by_role" in s and "quality" not in s and "body_location" not in s


def test_stats_breakdowns_follow_role(client):
    ph = _patient(client, "st9@example.com", consent=True); _case_with_image(client, ph)
    assert set(client.get("/api/cases/stats", headers=ph).json()["breakdowns"]) == {"status", "quality"}
    rh = _staff(client, "res9@example.com", "researcher")
    assert {"body_location", "model_version", "source"} <= set(client.get("/api/cases/stats", headers=rh).json()["breakdowns"])
    mh = _staff(client, "ml9@example.com", "ml_engineer")
    assert "body_location" not in client.get("/api/cases/stats", headers=mh).json()["breakdowns"]


def test_owner_or_opener_can_delete_but_not_other_roles(client):
    ph = _patient(client, "dl1@example.com")
    me = client.get("/api/auth/me", headers=ph).json()["id"]
    dh = _staff(client, "dl-derm@example.com", "dermatologist")
    cid = client.post("/api/cases", headers=dh, json={"patient_id": me}).json()["id"]
    other = _staff(client, "dl-derm2@example.com", "dermatologist")
    assert client.delete(f"/api/cases/{cid}", headers=other).status_code == 403            # sees it, did not open it
    assert client.delete(f"/api/cases/{cid}", headers=dh).status_code == 204               # clinician who opened it

