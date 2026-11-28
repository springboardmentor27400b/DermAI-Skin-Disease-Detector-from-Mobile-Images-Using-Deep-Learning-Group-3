import numpy as np

from app.preprocessing.lesion import detect_lesion, overlay, roi_square
from app.preprocessing.pipeline import preprocess


def skin(h=420, w=420, seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), (205, 150, 125), np.int16) + rng.integers(-12, 12, (h, w, 3))
    # lighting gradient across the photo
    img += (np.linspace(-25, 25, w)[None, :, None]).astype(np.int16)
    return img


def disc(img, cx, cy, r, col):
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    img[((yy - cy) ** 2 + (xx - cx) ** 2) < r * r] = col


def test_finds_central_lesion_despite_lighting_gradient():
    img = skin(); disc(img, 230, 200, 45, (100, 65, 55))
    r = detect_lesion(np.clip(img, 0, 255).astype(np.uint8))
    assert r.found and r.mask.shape == (420, 420)
    x0, y0, x1, y1 = r.bbox
    assert abs((x0 + x1) / 2 - 230) < 20 and abs((y0 + y1) / 2 - 200) < 20
    assert 0.03 < r.area_fraction < 0.12 and r.contrast_ratio > 3 and r.lesion_count == 1
    x, y, side = roi_square(r, (420, 420))
    assert x <= x0 and y <= y0 and x + side >= x1 and y + side >= y1      # ROI contains the lesion with context


def test_reports_second_spot_and_ignores_corner_noise():
    img = skin(); disc(img, 200, 210, 50, (95, 60, 50)); disc(img, 330, 120, 30, (110, 70, 60))
    r = detect_lesion(np.clip(img, 0, 255).astype(np.uint8))
    assert r.found and r.lesion_count >= 2 and len(r.other_boxes) >= 1


def test_plain_skin_has_no_lesion_and_falls_back_to_centre_crop():
    rgb = np.clip(skin(seed=3), 0, 255).astype(np.uint8)
    r = detect_lesion(rgb)
    assert not r.found
    assert roi_square(r, (420, 300)) == (0, 60, 300)
    assert preprocess(rgb, 128, lesion=r).steps[2] == "center_square_crop"


def test_overlay_and_roi_preprocess_shapes():
    img = skin(); disc(img, 210, 210, 40, (90, 55, 50)); rgb = np.clip(img, 0, 255).astype(np.uint8)
    r = detect_lesion(rgb)
    assert overlay(rgb, r).shape[:2] == (420, 420)
    p = preprocess(rgb, 256, lesion=r)
    assert p.preview_rgb.shape == (256, 256, 3) and "lesion_roi_crop" in p.steps


def test_gate_rejects_edge_blobs_and_thin_strips():
    img = skin(); disc(img, 12, 210, 40, (95, 60, 50))                    # blob cut by the frame edge
    assert not detect_lesion(np.clip(img, 0, 255).astype(np.uint8)).found
    img = skin(); img[60:80, 40:380] = (90, 60, 50)                        # shadow / crease strip
    assert not detect_lesion(np.clip(img, 0, 255).astype(np.uint8)).found


def test_deployed_segmenter_replaces_colour_model(tmp_path, monkeypatch):
    import json
    import pytest
    torch = pytest.importorskip("torch")
    from app.core.config import settings
    from app.inference import segmenter

    class Centre(torch.nn.Module):                     # "segments" a fixed central square, whatever the image
        def forward(self, x):
            m = torch.full_like(x[:, :1], -8.0)
            m[:, :, 40:88, 40:88] = 8.0
            return m
    torch.jit.trace(Centre(), torch.randn(1, 3, 128, 128), check_trace=False).save(str(tmp_path / "segmentation.ts.pt"))
    (tmp_path / "segmentation.json").write_text(json.dumps({"arch": "fake", "img_size": 128, "mean": [0.5] * 3, "std": [0.5] * 3}))
    monkeypatch.setattr(settings, "model_dir", str(tmp_path)); segmenter.reload()
    try:
        r = detect_lesion(np.clip(skin(), 0, 255).astype(np.uint8))
        assert r.found and r.method == "segmentation_model"
        x0, y0, x1, y1 = r.bbox
        assert abs(x0 - 40 / 128 * 420) < 25 and abs(x1 - 88 / 128 * 420) < 25
    finally:
        monkeypatch.undo(); segmenter.reload()


def test_roi_min_frac_keeps_small_detections_from_zooming_in():
    img = skin(); disc(img, 210, 210, 25, (90, 55, 50)); rgb = np.clip(img, 0, 255).astype(np.uint8)
    r = detect_lesion(rgb)
    assert r.found
    small = roi_square(r, (420, 420), min_frac=0.3)[2]
    wide = roi_square(r, (420, 420), min_frac=0.8)[2]
    assert wide >= int(0.8 * 420) - 1 and wide > small
    assert preprocess(rgb, 128, lesion=r, roi_min_frac=0.8).preview_rgb.shape == (128, 128, 3)


def test_trained_segmenter_is_not_blocked_by_the_colour_gate(tmp_path, monkeypatch):
    import json
    import pytest
    torch = pytest.importorskip("torch")
    from app.core.config import settings
    from app.inference import segmenter

    class Big(torch.nn.Module):                        # a large lesion touching the frame edge: legitimate for a trained model
        def forward(self, x):
            m = torch.full_like(x[:, :1], -8.0)
            m[:, :, 0:100, 10:118] = 8.0
            return m
    torch.jit.trace(Big(), torch.randn(1, 3, 128, 128), check_trace=False).save(str(tmp_path / "segmentation.ts.pt"))
    (tmp_path / "segmentation.json").write_text(json.dumps({"arch": "fake", "img_size": 128, "mean": [0.5] * 3, "std": [0.5] * 3}))
    monkeypatch.setattr(settings, "model_dir", str(tmp_path)); segmenter.reload()
    try:
        r = detect_lesion(np.clip(skin(), 0, 255).astype(np.uint8))
        assert r.found and r.method == "segmentation_model"
    finally:
        monkeypatch.undo(); segmenter.reload()

