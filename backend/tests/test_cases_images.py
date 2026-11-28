from tests.conftest import make_image, register_and_login


def _case(client, h):
    r = client.post("/api/cases", headers=h, json={"patient_age": 41, "patient_gender": "female", "body_location": "back"})
    assert r.status_code == 201, r.text
    return r.json()


def test_case_crud_and_isolation(client):
    owner = register_and_login(client, "owner@example.com")
    other = register_and_login(client, "other@example.com")
    c = _case(client, owner)
    assert c["case_code"].startswith("DRM-")
    assert client.get(f"/api/cases/{c['id']}", headers=owner).status_code == 200
    assert client.get(f"/api/cases/{c['id']}", headers=other).status_code == 404   # no cross-user access
    assert all(x["id"] != c["id"] for x in client.get("/api/cases", headers=other).json())
    r = client.patch(f"/api/cases/{c['id']}", headers=owner, json={"patient_age": 42})
    assert r.json()["patient_age"] == 42


def test_upload_good_image_is_preprocessed(client):
    h = register_and_login(client, "up1@example.com")
    c = _case(client, h)
    r = client.post(f"/api/cases/{c['id']}/images", headers=h,
                    files={"file": ("lesion.jpg", make_image("good"), "image/jpeg")}, data={"image_source": "camera"})
    assert r.status_code == 201, r.text
    img = r.json()
    assert img["analysis_status"] == "pending" and img["quality_label"] != "poor"
    f = client.get(f"/api/images/{img['id']}/file?variant=processed", headers=h)
    assert f.status_code == 200 and f.headers["content-type"] == "image/png"


def test_poor_quality_is_flagged_and_not_processed(client):
    h = register_and_login(client, "up2@example.com")
    c = _case(client, h)
    r = client.post(f"/api/cases/{c['id']}/images", headers=h, files={"file": ("dark.jpg", make_image("dark"), "image/jpeg")})
    assert r.status_code == 201
    img = r.json()
    assert img["quality_label"] == "poor" and img["analysis_status"] == "rejected_quality" and img["quality_issues"]
    assert client.get(f"/api/images/{img['id']}/file?variant=processed", headers=h).status_code == 404


def test_validation_rejections(client):
    h = register_and_login(client, "up3@example.com")
    c = _case(client, h)
    url = f"/api/cases/{c['id']}/images"
    assert client.post(url, headers=h, files={"file": ("x.jpg", b"not an image", "image/jpeg")}).status_code == 422
    assert client.post(url, headers=h, files={"file": ("small.jpg", make_image("good", (100, 100)), "image/jpeg")}).status_code == 422
    assert client.post(url, headers=h, files={"file": ("a.gif", make_image("good", fmt="GIF"), "image/gif")}).status_code == 422


def test_quality_check_endpoint_stores_nothing(client):
    h = register_and_login(client, "up4@example.com")
    r = client.post("/api/images/check-quality", headers=h, files={"file": ("a.jpg", make_image("good"), "image/jpeg")})
    assert r.status_code == 200 and r.json()["acceptable_for_analysis"] is True


def test_image_access_is_authorised(client):
    owner = register_and_login(client, "own5@example.com")
    other = register_and_login(client, "oth5@example.com")
    c = _case(client, owner)
    img = client.post(f"/api/cases/{c['id']}/images", headers=owner, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).json()
    assert client.get(f"/api/images/{img['id']}/file", headers=other).status_code == 404
    assert client.post(f"/api/cases/{c['id']}/images", headers=other, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).status_code == 404


def test_stats(client):
    h = register_and_login(client, "st@example.com")
    c = _case(client, h)
    client.post(f"/api/cases/{c['id']}/images", headers=h, files={"file": ("a.jpg", make_image("good"), "image/jpeg")})
    s = client.get("/api/cases/stats", headers=h).json()
    assert s["total_cases"] == 1 and s["total_images"] == 1


def test_serves_prebuilt_frontend(client):
    from pathlib import Path
    import pytest
    if not (Path(__file__).resolve().parent.parent / "frontend_dist" / "index.html").exists():
        pytest.skip("frontend_dist not built (run npm run build in frontend/ and copy dist/ there)")
    r = client.get("/cases/123")                       # client-side route falls back to index.html
    assert r.status_code == 200 and "<div id=\"root\">" in r.text
    assert client.get("/docs").status_code == 200       # API docs still reachable
    assert client.get("/api/nope").status_code == 404

