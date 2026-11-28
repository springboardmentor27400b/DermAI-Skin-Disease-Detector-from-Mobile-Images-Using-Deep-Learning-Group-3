"""Upload -> lesion detection -> classification, using a tiny TorchScript model written on the fly."""
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from app.core.config import settings                    # noqa: E402
from app.inference import classifier                      # noqa: E402
from tests.conftest import make_image, register_and_login  # noqa: E402

CLASSES = ["ACK", "BCC", "MEL", "NEV", "SCC", "SEK"]
PW = "Passw0rdX"


@pytest.fixture()
def deployed_model():
    d = Path(settings.model_dir) / "v-test"
    d.mkdir(parents=True, exist_ok=True)
    net = torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(4), torch.nn.Flatten(), torch.nn.Linear(48, 6)).eval()
    torch.jit.trace(net, torch.randn(1, 3, 64, 64), check_trace=False).save(str(d / "model.ts.pt"))
    (d / "meta.json").write_text(json.dumps({"arch": "tiny", "classes": CLASSES, "class_names": {c: c + " name" for c in CLASSES}, "img_size": 64,
                                             "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225], "temperature": 1.5,
                                             "dataset": "test", "evaluation": {"macro_f1": 0.5}}))
    (Path(settings.model_dir) / "active.json").write_text(json.dumps({"version": "v-test"}))
    classifier.reload()
    yield
    (Path(settings.model_dir) / "active.json").unlink()
    classifier.reload()


def _case(client, h):
    return client.post("/api/cases", headers=h, json={"body_location": "arm"}).json()["id"]


def _upload(client, h, cid, kind="good"):
    return client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("a.jpg", make_image(kind), "image/jpeg")})


def test_without_a_model_images_stay_pending_but_lesion_is_detected(client):
    classifier.reload()
    h = register_and_login(client, "an0@example.com")
    r = _upload(client, h, _case(client, h))
    img = r.json()
    assert r.status_code == 201 and img["analysis_status"] == "pending" and img["prediction_result"] is None
    assert img["lesion_info"]["found"] is True
    assert client.get(f"/api/images/{img['id']}/file?variant=lesion", headers=h).status_code == 200
    assert client.get("/api/models/active", headers=h).json()["available"] is False


def test_upload_is_classified_and_calibrated(client, deployed_model):
    h = register_and_login(client, "an1@example.com")
    img = _upload(client, h, _case(client, h)).json()
    assert img["analysis_status"] == "completed" and img["model_version"] is None   # patients never see versions
    p = img["prediction_result"]
    assert p["label"] in CLASSES and len(p["top_n"]) == 3 and abs(sum(p["probabilities"].values()) - 1) < 0.01
    assert p["top_n"][0]["probability"] >= p["top_n"][1]["probability"] and "not a medical diagnosis" in p["disclaimer"]
    assert p["model"]["temperature"] == 1.5 and p["model"]["version"] == "v-test"


def test_poor_quality_is_never_classified(client, deployed_model):
    h = register_and_login(client, "an2@example.com")
    img = _upload(client, h, _case(client, h), "dark").json()
    assert img["analysis_status"] == "rejected_quality" and img["prediction_result"] is None and img["lesion_info"] is None


def test_reanalyze_and_admin_visibility(client, deployed_model):
    h = register_and_login(client, "an3@example.com")
    cid = _case(client, h)
    iid = _upload(client, h, cid).json()["id"]
    r = client.post(f"/api/images/{iid}/analyze", headers=h)
    assert r.status_code == 200 and r.json()["analysis_status"] == "completed"
    other = register_and_login(client, "an4@example.com")
    assert client.post(f"/api/images/{iid}/analyze", headers=other).status_code == 404
    a = client.post("/api/auth/login", data={"username": "admin@dermai.local", "password": "ChangeMe!2026"}).json()["access_token"]
    ah = {"Authorization": f"Bearer {a}"}
    img = client.get(f"/api/cases/{cid}", headers=ah).json()["images"][0]
    assert img["prediction_result"] is None and img["lesion_info"] is None       # admins see operations only
    assert client.get(f"/api/images/{iid}/file?variant=lesion", headers=ah).status_code == 403
    assert "evaluation" not in client.get("/api/models/active", headers=h).json()   # hidden from patients
    assert client.get("/api/models/active", headers=ah).json()["evaluation"]["macro_f1"] == 0.5


def test_admin_reanalyze_pending_after_deployment(client):
    classifier.reload()
    h = register_and_login(client, "an5@example.com")
    cid = _case(client, h)
    iid = _upload(client, h, cid).json()["id"]                      # no model yet -> pending
    ah = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username': 'admin@dermai.local', 'password': 'ChangeMe!2026'}).json()['access_token']}"}
    assert client.post("/api/models/reanalyze", headers=h).status_code == 403
    d = Path(settings.model_dir) / "v-late"; d.mkdir(parents=True, exist_ok=True)
    net = torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(2), torch.nn.Flatten(), torch.nn.Linear(12, 6)).eval()
    torch.jit.trace(net, torch.randn(1, 3, 64, 64), check_trace=False).save(str(d / "model.ts.pt"))
    (d / "meta.json").write_text(json.dumps({"arch": "tiny", "classes": CLASSES, "img_size": 64, "mean": [0.5] * 3, "std": [0.5] * 3}))
    (Path(settings.model_dir) / "active.json").write_text(json.dumps({"version": "v-late"}))
    classifier.reload()
    try:
        assert client.post("/api/models/reanalyze", headers=ah).json()["processed"] >= 1
        ah_img = client.get(f"/api/cases/{cid}", headers=ah).json()["images"][0]
        assert ah_img["model_version"] == "v-late" and ah_img["analysis_status"] == "completed"
        assert client.get(f"/api/cases/{cid}", headers=h).json()["images"][0]["prediction_result"]["model"]["version"] == "v-late"
    finally:
        (Path(settings.model_dir) / "active.json").unlink(); classifier.reload()


def test_preprocessing_recipe_follows_the_model(client):
    d = Path(settings.model_dir) / "v-recipe"; d.mkdir(parents=True, exist_ok=True)
    net = torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(2), torch.nn.Flatten(), torch.nn.Linear(12, 6)).eval()
    torch.jit.trace(net, torch.randn(1, 3, 64, 64), check_trace=False).save(str(d / "model.ts.pt"))
    (d / "meta.json").write_text(json.dumps({"arch": "t", "classes": CLASSES, "img_size": 64, "mean": [0.5] * 3, "std": [0.5] * 3,
                                             "preprocessing": "size=192 enhance=False lesion_roi=False hair_removal=False"}))
    (Path(settings.model_dir) / "active.json").write_text(json.dumps({"version": "v-recipe"}))
    classifier.reload()
    try:
        assert classifier.preprocessing_flags() == {"size": 192, "enhance": False, "lesion_roi": False, "hair_removal": False, "roi_min": 0.3}
        h = register_and_login(client, "an6@example.com")
        img = _upload(client, h, _case(client, h)).json()
        assert img["analysis_status"] == "completed" and not any("lesion could not" in c for c in img["prediction_result"]["caveats"])
    finally:
        (Path(settings.model_dir) / "active.json").unlink(); classifier.reload()
    assert classifier.preprocessing_flags() == {"size": settings.roi_size, "enhance": True, "lesion_roi": True, "hair_removal": True, "roi_min": 0.3}

