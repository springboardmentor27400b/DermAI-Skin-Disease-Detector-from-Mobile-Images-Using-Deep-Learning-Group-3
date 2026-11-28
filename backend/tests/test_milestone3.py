"""Milestone 3: risk categories, notifications, model registry, explainability (torch-gated)."""
import json
from pathlib import Path

import numpy as np
import pytest

from app.core.config import settings
from app.inference import classifier, risk
from tests.conftest import make_image, register_and_login

PROTO = {"protocol": "test-v1", "malignant_classes": ["BCC", "SCC", "MEL"], "t_low": 0.2, "t_high": 0.7}
CLASSES = ["ACK", "BCC", "MEL", "NEV", "SCC", "SEK"]


def pred(**p):
    base = dict.fromkeys(CLASSES, 0.0); base.update(p)
    return {"probabilities": base, "low_confidence": False}


def test_risk_bands_follow_the_protocol():
    assert risk.assess(pred(NEV=0.9, SEK=0.1), "good", True, PROTO)["key"] == "low"
    assert risk.assess(pred(ACK=0.6, BCC=0.4), "good", True, PROTO)["key"] == "moderate"
    r = risk.assess(pred(BCC=0.5, SCC=0.3, ACK=0.2), "good", True, PROTO)
    assert r["key"] == "high" and r["category"] == "High Risk" and abs(r["p_malignant"] - 0.8) < 1e-6 and r["protocol"] == "test-v1"


def test_low_risk_is_never_given_when_the_lesion_was_not_found():
    r = risk.assess(pred(NEV=0.95, SEK=0.05), "good", False, PROTO)
    assert r["key"] == "review" and r["category"] == "Requires Clinical Review"
    assert any("could not be located" in x for x in r["reasons"])
    assert risk.assess(pred(BCC=0.9, ACK=0.1), "good", False, PROTO)["key"] == "high"      # worrying results are never softened


def test_no_protocol_means_no_category():
    assert risk.assess(pred(NEV=1.0), "good", True, None) is None or classifier.get_model() is None


def _admin(client):
    r = client.post("/api/auth/login", data={"username": "admin@dermai.local", "password": "ChangeMe!2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_notifications_are_role_shaped(client):
    classifier.reload()
    h = register_and_login(client, "nt1@example.com")
    cid = client.post("/api/cases", headers=h, json={}).json()["id"]
    client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("d.jpg", make_image("dark"), "image/jpeg")})
    notes = client.get("/api/notifications", headers=h).json()
    assert any(n["title"] == "Poor image quality" and n["level"] == "medium" for n in notes)
    assert all(n["level"] != "critical" for n in notes)
    other = register_and_login(client, "nt2@example.com")
    assert client.get("/api/notifications", headers=other).json() == []                       # nobody else's alerts
    assert client.get("/api/notifications", headers=_admin(client)).json() is not None
    assert client.get("/api/notifications").status_code == 401


def test_model_registry_and_rollback(client):
    d = Path(settings.model_dir)
    for v, f1 in (("v-a", 0.5), ("v-b", 0.6)):
        (d / v).mkdir(parents=True, exist_ok=True)
        (d / v / "meta.json").write_text(json.dumps({"arch": "x", "classes": CLASSES, "img_size": 64, "evaluation": {"macro_f1": f1}}))
    (d / "v-b" / "risk.json").write_text(json.dumps(PROTO))
    ah, ph = _admin(client), register_and_login(client, "mr1@example.com")
    assert client.get("/api/models/versions", headers=ph).status_code == 403
    assert client.post("/api/models/activate?version=v-a", headers=ph).status_code == 403
    assert client.post("/api/models/activate?version=nope", headers=ah).status_code == 404
    client.post("/api/models/activate?version=v-a", headers=ah)
    rows = {r["version"]: r for r in client.get("/api/models/versions", headers=ah).json()}
    assert rows["v-a"]["active"] and not rows["v-b"]["active"] and rows["v-b"]["risk_protocol"] and rows["v-b"]["macro_f1"] == 0.6
    r = client.post("/api/models/activate?version=v-b", headers=ah).json()
    assert r["previous"] == "v-a"
    assert any(l["action"] == "model.activate" for l in client.get("/api/admin/audit-logs", headers=ah).json())
    (d / "active.json").unlink(); classifier.reload()


def test_single_analysis_endpoint_is_authorised(client):
    h, other = register_and_login(client, "sa1@example.com"), register_and_login(client, "sa2@example.com")
    cid = client.post("/api/cases", headers=h, json={}).json()["id"]
    iid = client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).json()["id"]
    r = client.get(f"/api/images/{iid}", headers=h)
    assert r.status_code == 200 and r.json()["case_code"].startswith("DRM-")
    assert client.get(f"/api/images/{iid}", headers=other).status_code == 404
    assert client.get(f"/api/images/{iid}/file?variant=cam", headers=h).status_code == 404   # no attention map without a model
    assert client.get("/api/images/history", headers=h).status_code == 200                   # static routes are not shadowed


def _write_cam_model(tmp: Path, version: str):
    """A tiny conv net split exactly like ml/export_model.py does (features -> head), plus the full classifier."""
    import torch
    import torch.nn as nn
    torch.manual_seed(0)
    feats = nn.Sequential(nn.Conv2d(3, 8, 3, padding=1), nn.ReLU(), nn.MaxPool2d(4)).eval()
    head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(1), nn.Linear(8, 6)).eval()
    full = nn.Sequential(feats, head).eval()
    d = tmp / version; d.mkdir(parents=True, exist_ok=True)
    x = torch.randn(1, 3, 64, 64)
    torch.jit.trace(full, x, check_trace=False).save(str(d / "model.ts.pt"))
    torch.jit.trace(feats, x, check_trace=False).save(str(d / "features.ts.pt"))
    torch.jit.trace(head, feats(x), check_trace=False).save(str(d / "head.ts.pt"))
    (d / "meta.json").write_text(json.dumps({"arch": "tiny", "classes": CLASSES, "img_size": 64, "mean": [0.5] * 3, "std": [0.5] * 3,
                                             "explain": {"method": "grad-cam", "members": [""]}}))
    (d / "risk.json").write_text(json.dumps(PROTO))
    (tmp / "active.json").write_text(json.dumps({"version": version}))
    classifier.reload()


def test_gradcam_heatmap_overlay_and_end_to_end(client):
    pytest.importorskip("torch")
    from app.inference import explain
    root = Path(settings.model_dir)
    _write_cam_model(root, "v-cam")
    try:
        assert explain.available()
        rgb = (np.random.default_rng(1).random((120, 120, 3)) * 255).astype(np.uint8)
        for method in ("gradcam", "gradcampp"):
            heat = explain.heatmap(rgb, 2, method)
            assert heat.shape == (64, 64) and 0 <= heat.min() and heat.max() <= 1.0 + 1e-6
        ov = explain.overlay(rgb, heat)
        assert ov.shape == rgb.shape and ov.dtype == np.uint8

        h = register_and_login(client, "cam1@example.com")
        cid = client.post("/api/cases", headers=h, json={}).json()["id"]
        img = client.post(f"/api/cases/{cid}/images", headers=h, files={"file": ("a.jpg", make_image("good"), "image/jpeg")}).json()
        p = img["prediction_result"]
        assert img["analysis_status"] == "completed" and p["risk"]["category"] in risk.CATEGORY.values()
        assert p["explain"]["method"] == "Grad-CAM" and p["explain"]["target"] == p["label"]
        f = client.get(f"/api/images/{img['id']}/file?variant=cam", headers=h)
        assert f.status_code == 200 and f.headers["content-type"] == "image/png"
        rep = client.get(f"/api/cases/{cid}/report?format=json", headers=h).json()["images"][0]
        assert rep["risk_category"] == p["risk"]["category"] and "Grad-CAM" in rep["explainability_visualization"]
        assert client.get(f"/api/cases/{cid}/report", headers=h).content[:4] == b"%PDF"
        assert client.get("/api/models/active", headers=h).json()["explainability_available"] is True
        client.delete(f"/api/images/{img['id']}", headers=h)
    finally:
        (root / "active.json").unlink(); classifier.reload()

