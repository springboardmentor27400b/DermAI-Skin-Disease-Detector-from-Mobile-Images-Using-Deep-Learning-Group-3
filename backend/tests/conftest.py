import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["PROCESSED_DIR"] = f"{_tmp}/processed"
os.environ["MODEL_DIR"] = f"{_tmp}/models"

from io import BytesIO  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def make_image(kind: str = "good", size=(400, 400), fmt="JPEG") -> bytes:
    rng = np.random.default_rng(0)
    h, w = size[1], size[0]
    if kind == "good":      # textured skin-like patch with a darker lesion
        base = np.full((h, w, 3), (205, 150, 125), np.uint8).astype(np.int16)
        base += rng.integers(-25, 25, (h, w, 3), dtype=np.int16)
        yy, xx = np.ogrid[:h, :w]
        base[((yy - h // 2) ** 2 + (xx - w // 2) ** 2) < (min(h, w) // 5) ** 2] = (95, 60, 50)
        arr = np.clip(base, 0, 255).astype(np.uint8)
    elif kind == "dark":
        arr = np.clip(rng.normal(12, 3, (h, w, 3)), 0, 255).astype(np.uint8)
    elif kind == "flat":    # uniform = no detail/blur-like
        arr = np.full((h, w, 3), (180, 140, 120), np.uint8)
    else:
        raise ValueError(kind)
    buf = BytesIO()
    Image.fromarray(arr).save(buf, format=fmt)
    return buf.getvalue()


def register_and_login(client, email="pat@example.com", password="Passw0rdX", role="patient"):
    client.post("/api/auth/register", json={"email": email, "full_name": "Test User", "password": password, "role": role})
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

