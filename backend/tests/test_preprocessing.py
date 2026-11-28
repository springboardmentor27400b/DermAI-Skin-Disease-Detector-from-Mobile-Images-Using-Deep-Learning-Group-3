import numpy as np
from PIL import Image

from app.preprocessing.pipeline import center_square_crop, preprocess, to_rgb_array
from app.preprocessing.quality import assess_quality
from tests.conftest import make_image
from io import BytesIO


def _rgb(kind):
    return to_rgb_array(Image.open(BytesIO(make_image(kind))))


def test_pipeline_shapes_and_normalisation():
    r = preprocess(_rgb("good"), 224)
    assert r.preview_rgb.shape == (224, 224, 3) and r.preview_rgb.dtype == np.uint8
    assert r.model_input.shape == (3, 224, 224) and r.model_input.dtype == np.float32
    assert abs(float(r.model_input.mean())) < 2.0
    assert "clahe_contrast" in r.steps


def test_center_crop_non_square():
    assert center_square_crop(np.zeros((300, 500, 3), np.uint8)).shape == (300, 300, 3)


def test_exif_orientation_is_applied():
    img = Image.new("RGB", (300, 200), (200, 150, 120))
    exif = img.getexif(); exif[0x0112] = 6           # rotate 270 -> portrait
    buf = BytesIO(); img.save(buf, format="JPEG", exif=exif)
    assert to_rgb_array(Image.open(BytesIO(buf.getvalue()))).shape[:2] == (300, 200)


def test_quality_labels():
    assert assess_quality(_rgb("good")).label in {"good", "acceptable"}
    q = assess_quality(_rgb("dark"))
    assert q.label == "poor" and any("dark" in i.lower() for i in q.issues)
    assert assess_quality(_rgb("flat")).label == "poor"      # no detail at all


def test_thresholds_are_configurable_and_exposed(client):
    from app.core.config import settings
    from app.preprocessing import quality
    assert quality.BLUR_POOR == settings.quality_blur_poor and quality.CONTRAST_POOR == settings.quality_contrast_poor
    assert quality.BLUR_POOR < quality.BLUR_ACCEPTABLE and quality.CONTRAST_POOR < quality.CONTRAST_ACCEPTABLE
    from tests.conftest import register_and_login
    h = register_and_login(client, "thr@example.com")
    t = client.get("/api/images/quality-thresholds", headers=h).json()
    assert t["blur"] == [settings.quality_blur_poor, settings.quality_blur_acceptable]
    assert client.get("/api/images/quality-thresholds").status_code == 401


def test_hair_removed_but_small_lesion_kept():
    import cv2
    from app.preprocessing.hair import hair_mask, remove_hair
    rng = np.random.default_rng(0)
    img = np.clip(np.full((400, 400, 3), (205, 150, 125), np.int16) + rng.integers(-8, 8, (400, 400, 3)), 0, 255).astype(np.uint8)
    yy, xx = np.ogrid[:400, :400]
    img[((yy - 200) ** 2 + (xx - 200) ** 2) < 12 ** 2] = (60, 40, 35)
    for _ in range(8):
        cv2.line(img, (int(rng.integers(0, 400)), 0), (int(rng.integers(0, 400)), 399), (90, 60, 45), 2)
    mask, frac = hair_mask(img)
    assert frac > 0.02 and mask[190:210, 190:210].sum() == 0
    out, _ = remove_hair(img)
    assert (out.sum(2) < 330).sum() < 0.5 * (img.sum(2) < 330).sum() and tuple(out[200, 200]) == (60, 40, 35)


def test_extra_quality_flags_are_informational_only():
    skin = _rgb("good")
    assert assess_quality(skin).skin_fraction > 0.8
    padded = np.pad(skin, ((60, 60), (0, 0), (0, 0)))                         # black bars top and bottom
    q = assess_quality(padded)
    assert any("blank borders" in i for i in q.issues) and q.label in {"good", "acceptable"}
    blue = np.full((400, 400, 3), (40, 60, 200), np.uint8); blue[::7] = (60, 80, 220)
    assert any("not skin" in i for i in assess_quality(blue).issues)

