"""End-to-end journey through the real API: patient -> clinician -> researcher -> administrator, with reports and history."""
from tests.conftest import make_image

PW = "Passw0rdX"


def _login(client, email, password=PW):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_workflow(client):
    admin = _login(client, "admin@dermai.local", "ChangeMe!2026")
    # 1. a patient signs up, opts in to research, and submits a case with two photos (one good, one too dark)
    assert client.post("/api/auth/register", json={"email": "e2e-pat@example.com", "full_name": "E2E Patient", "password": PW, "role": "patient",
                                                   "age": 52, "research_consent": True}).status_code == 201
    pat = _login(client, "e2e-pat@example.com")
    cid = client.post("/api/cases", headers=pat, json={"body_location": "back", "medical_history": "eczema"}).json()["id"]
    q = client.post("/api/images/check-quality", headers=pat, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).json()
    assert q["acceptable_for_analysis"]
    good = client.post(f"/api/cases/{cid}/images", headers=pat, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}, data={"image_source": "camera"}).json()
    dark = client.post(f"/api/cases/{cid}/images", headers=pat, files={"file": ("d.jpg", make_image("dark"), "image/jpeg")}).json()
    assert good["analysis_status"] in ("pending", "completed") and dark["analysis_status"] == "rejected_quality"
    assert any(n["title"] == "Poor image quality" for n in client.get("/api/notifications", headers=pat).json())

    # 2. an administrator creates a clinician; the clinician sees the case and adds a note
    assert client.post("/api/admin/users", headers=admin, json={"email": "e2e-doc@example.com", "full_name": "Dr E2E", "password": PW, "role": "dermatologist"}).status_code == 201
    doc = _login(client, "e2e-doc@example.com")
    detail = client.get(f"/api/cases/{cid}", headers=doc).json()
    assert detail["owner_name"] == "E2E Patient" and len(detail["images"]) == 2
    assert client.post(f"/api/cases/{cid}/notes", headers=doc, json={"text": "Review in 4 weeks"}).status_code == 201
    assert client.get(f"/api/cases/{cid}", headers=pat).json()["notes"] == []                 # the patient never receives clinical notes

    # 3. reports in all three formats, shaped by role
    for fmt, magic in (("pdf", b"%PDF"), ("json", b"{"), ("csv", b"\xef\xbb\xbf")):
        r = client.get(f"/api/cases/{cid}/report?format={fmt}", headers=doc)
        assert r.status_code == 200 and r.content.startswith(magic), fmt
    assert client.get(f"/api/cases/{cid}/report?format=json", headers=doc).json()["case"]["medical_history"] == "eczema"

    # 4. a researcher sees the de-identified case only because the patient consented
    assert client.post("/api/admin/users", headers=admin, json={"email": "e2e-res@example.com", "full_name": "Res E2E", "password": PW, "role": "researcher"}).status_code == 201
    res = _login(client, "e2e-res@example.com")
    shared = client.get(f"/api/cases/{cid}", headers=res).json()
    assert shared["owner_name"] is None and shared["patient_age"] is None and shared["medical_history"] is None
    client.patch("/api/auth/me", headers=pat, json={"research_consent": False})
    assert client.get(f"/api/cases/{cid}", headers=res).status_code == 404

    # 5. history and audit trail
    hist = client.get("/api/images/history", headers=doc).json()
    assert len([h for h in hist if h["case_id"] == cid]) == 2
    actions = {l["action"] for l in client.get("/api/admin/audit-logs?limit=500", headers=admin).json()}
    assert {"user.register", "auth.login", "case.create", "image.upload", "case.note_add", "report.generate"} <= actions

    # 6. deleting the case removes it for everyone
    assert client.delete(f"/api/cases/{cid}", headers=pat).status_code == 204
    assert client.get(f"/api/cases/{cid}", headers=doc).status_code == 404
