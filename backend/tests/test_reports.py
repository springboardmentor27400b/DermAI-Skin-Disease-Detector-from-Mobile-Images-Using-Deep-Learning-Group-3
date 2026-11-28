import csv
import io
import json

from tests.conftest import make_image, register_and_login

PW = "Passw0rdX"


def _setup(client, email):
    h = register_and_login(client, email)
    cid = client.post("/api/cases", headers=h, json={"body_location": "arm", "patient_age": 40, "medical_history": "asthma"}).json()["id"]
    client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("secret.jpg", make_image("good"), "image/jpeg")}, data={"capture_date": "2026-05-01", "image_source": "camera"})
    return h, cid


def test_pdf_json_csv_reports(client):
    h, cid = _setup(client, "rp1@example.com")
    pdf = client.get(f"/api/cases/{cid}/report", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and "attachment" in pdf.headers["content-disposition"]
    j = client.get(f"/api/cases/{cid}/report?format=json", headers=h).json()
    assert j["case"]["case_code"].startswith("DRM-") and "not a medical diagnosis" in j["disclaimer"]
    im = j["images"][0]
    assert im["image_quality"]["label"] and im["detected_lesion"] is not None and im["risk_category"] == "Not available in this version"
    assert "model_version" in im and im["model_version"] is None and "_id" not in im and im["image_id"] is None   # patient: no ids/versions
    rows = list(csv.DictReader(io.StringIO(client.get(f"/api/cases/{cid}/report?format=csv", headers=h).content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["case_code"] == j["case"]["case_code"]
    assert client.get(f"/api/cases/{cid}/report?format=xml", headers=h).status_code == 422


def test_reports_respect_roles_and_ownership(client):
    h, cid = _setup(client, "rp2@example.com")
    other = register_and_login(client, "rp3@example.com")
    assert client.get(f"/api/cases/{cid}/report", headers=other).status_code == 404
    assert client.get(f"/api/cases/{cid}/report?image_id=99999", headers=h).status_code == 404
    a = client.post("/api/auth/login", data={"username": "admin@dermai.local", "password": "ChangeMe!2026"}).json()["access_token"]
    ah = {"Authorization": f"Bearer {a}"}
    ja = client.get(f"/api/cases/{cid}/report?format=json", headers=ah).json()
    assert "patient_age" not in ja["case"] and "medical_history" not in ja["case"] and ja["images"][0]["image_quality"]["label"] is None
    assert client.get(f"/api/cases/{cid}/report", headers=ah).content[:4] == b"%PDF"             # admin PDF has no images, no clinical data
    r = client.post("/api/admin/users", headers=ah, json={"email": "rpd@example.com", "full_name": "Dr R", "password": PW, "role": "dermatologist"})
    dh = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username': 'rpd@example.com', 'password': PW}).json()['access_token']}"}
    jd = client.get(f"/api/cases/{cid}/report?format=json", headers=dh).json()
    assert jd["case"]["medical_history"] == "asthma" and jd["images"][0]["image_id"].startswith("IMG-")

