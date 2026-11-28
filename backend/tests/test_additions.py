"""Additions: logout revocation, notification read state, confidence breakdown, saliency + stability, lesion-visibility flag, registry details."""
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.core.config import settings
from app.inference import classifier
from tests.conftest import make_image, register_and_login

PW = "Passw0rdX"


def _login(client, email, password=PW):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client):
    return _login(client, "admin@dermai.local", "ChangeMe!2026")


def test_logout_revokes_only_that_token(client):
    register_and_login(client, "add-lo@example.com")
    h1, h2 = _login(client, "add-lo@example.com"), _login(client, "add-lo@example.com")      # two sessions
    assert client.get("/api/auth/me", headers=h1).status_code == 200
    assert client.post("/api/auth/logout", headers=h1).status_code == 204
    assert client.get("/api/auth/me", headers=h1).status_code == 401           # signed-out token is dead
    assert client.get("/api/auth/me", headers=h2).status_code == 200           # the other session is untouched
    assert client.post("/api/auth/logout").status_code == 401                  # needs a valid token
    actions = {l["action"] for l in client.get("/api/admin/audit-logs?limit=500", headers=_admin(client)).json()}
    assert "auth.logout" in actions


def test_notifications_can_be_marked_read_per_user(client):
    classifier.reload()
    h = register_and_login(client, "add-nr@example.com")
    cid = client.post("/api/cases", headers=h, json={}).json()["id"]
    client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("d.jpg", make_image("dark"), "image/jpeg")})
    notes = client.get("/api/notifications", headers=h).json()
    assert notes and all(n["read"] is False for n in notes)
    key = notes[0]["key"]
    assert client.post("/api/notifications/read", headers=h, json={"keys": [key, "no-such-key"]}).status_code == 204
    assert client.post("/api/notifications/read", headers=h, json={"keys": [key]}).status_code == 204       # idempotent
    after = {n["key"]: n["read"] for n in client.get("/api/notifications", headers=h).json()}
    assert after[key] is True and not all(after.values()) or len(after) == 1
    assert client.post("/api/notifications/read", json={"keys": [key]}).status_code == 401
    assert client.post("/api/notifications/read", headers=h, json={"keys": ["x" * 65]}).status_code == 422


def test_plain_skin_gets_lesion_visibility_flag_without_changing_the_label(client):
    classifier.reload()
    from tests.test_lesion import skin                                            # plain skin with a lighting gradient, no lesion
    arr = np.clip(skin(seed=3), 0, 255).astype(np.uint8)
    buf = BytesIO(); Image.fromarray(arr).save(buf, format="JPEG")
    h = register_and_login(client, "add-lv@example.com")
    cid = client.post("/api/cases", headers=h, json={}).json()["id"]
    img = client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("p.jpg", buf.getvalue(), "image/jpeg")}).json()
    assert any("lesion could not be located" in i for i in img["quality_issues"])
    assert img["quality_label"] in ("good", "acceptable")                       # informational only
    good = client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("g.jpg", make_image("good"), "image/jpeg")}).json()
    assert not any("lesion could not" in i for i in good["quality_issues"])


def test_registry_shows_training_details(client):
    d = Path(settings.model_dir) / "v-train"; d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps({"arch": "x", "classes": ["A"], "img_size": 64, "best_epoch": 17, "folds_sha256": "abc123", "n_train": 1379,
                                             "args": {"epochs": 30, "lr": None, "imbalance": "sampler", "aug": "basic", "seed": 42, "cache": "secret/path"}}))
    row = next(r for r in client.get("/api/models/versions", headers=_admin(client)).json() if r["version"] == "v-train")
    assert row["training"]["best_epoch"] == 17 and row["training"]["folds_sha256"] == "abc123" and row["training"]["imbalance"] == "sampler"
    assert "cache" not in row["training"]                                        # file paths are not exposed


torch = pytest.importorskip("torch")
from tests.test_milestone3 import _write_cam_model   # noqa: E402


@pytest.fixture()
def cam_model():
    root = Path(settings.model_dir)
    _write_cam_model(root, "v-add")
    yield
    (root / "active.json").unlink(missing_ok=True); classifier.reload()


def test_saliency_and_stability_end_to_end(client, cam_model):
    h = register_and_login(client, "add-sal@example.com")
    cid = client.post("/api/cases", headers=h, json={}).json()["id"]
    img = client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).json()
    p = img["prediction_result"]
    assert p["saliency"] == {"method": "Gradient saliency", "target": p["label"]}
    st = p["explain"].get("stability")
    assert st is None or -1.0 <= st <= 1.0
    f = client.get(f"/api/images/{img['id']}/file?variant=saliency", headers=h)
    assert f.status_code == 200 and f.headers["content-type"] == "image/png"
    rep = client.get(f"/api/cases/{cid}/report?format=json", headers=h).json()["images"][0]
    assert rep["explanation_stability"] == st
    assert client.get(f"/api/cases/{cid}/report", headers=h).content[:4] == b"%PDF"
    assert client.delete(f"/api/images/{img['id']}", headers=h).status_code == 204


def test_saliency_and_stability_functions(cam_model):
    from app.inference import explain
    rgb = (np.random.default_rng(1).random((120, 120, 3)) * 255).astype(np.uint8)
    sal = explain.saliency(rgb, 2)
    assert sal.shape == (64, 64) and sal.dtype == np.float32 and 0 <= sal.min() and sal.max() <= 1.0 and sal.max() > 0
    assert explain.saliency_overlay(rgb, sal).shape == rgb.shape
    heat = explain.heatmap(rgb, 2)
    s = explain.stability(rgb, 2, heat)                                           # real (random) model: any value in range, or None
    assert s is None or -1.0 <= s <= 1.0


def test_stability_metric_extremes(monkeypatch):
    """Stability = correlation between the map and the mirrored-photo map flipped back. Check it with maps whose answer is known."""
    from app.inference import explain
    rgb = (np.random.default_rng(2).random((64, 64, 3)) * 255).astype(np.uint8)
    follows = lambda img, idx, method=None: img.mean(2).astype(np.float32)        # moves with the image: perfectly consistent
    monkeypatch.setattr(explain, "heatmap", follows)
    assert explain.stability(rgb, 0, follows(rgb, 0)) == pytest.approx(1.0, abs=1e-6)
    left = np.zeros((64, 64), np.float32); left[:, :32] = 1
    fixed = lambda img, idx, method=None: left                                    # ignores the image: breaks when mirrored
    monkeypatch.setattr(explain, "heatmap", fixed)
    assert explain.stability(rgb, 0, left) == pytest.approx(-1.0, abs=1e-6)
    monkeypatch.setattr(explain, "heatmap", lambda img, idx, method=None: np.zeros((64, 64), np.float32))
    assert explain.stability(rgb, 0, left) is None                                # flat map: undefined


def test_confidence_breakdown_is_role_shaped(client, cam_model):
    ph = register_and_login(client, "add-cf@example.com")
    cid = client.post("/api/cases", headers=ph, json={}).json()["id"]
    client.post(f"/api/cases/{cid}/images", headers=ph, files={"file": ("a.jpg", make_image("good"), "image/jpeg")})
    assert "confidence" not in client.get("/api/cases/stats", headers=ph).json()["breakdowns"]
    ah = _admin(client)
    assert client.post("/api/admin/users", headers=ah, json={"email": "add-cfd@example.com", "full_name": "Dr Conf", "password": PW, "role": "dermatologist"}).status_code == 201
    dh = _login(client, "add-cfd@example.com")
    conf = client.get("/api/cases/stats", headers=dh).json()["breakdowns"]["confidence"]
    assert sum(conf.values()) >= 1 and set(conf) <= {"under 50%", "50-70%", "70-90%", "90% or more"}
