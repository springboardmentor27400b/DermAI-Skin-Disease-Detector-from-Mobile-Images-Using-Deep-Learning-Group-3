"""Contact sheets of lesion detection results, to judge the segmentation by eye (PAD-UFES-20 has no masks).

    python segment_review.py --images data/pad_ufes_20/images --n 48 --seed 1
    python segment_review.py --images ... --masks path/to/masks   # optional: Dice / IoU against masks named <image_stem>.png

Green outline = lesion mask, white square = ROI the classifier sees, orange boxes = other detected spots.
Look for: outlines on the wrong thing (hair, shadows, clothing), ROIs that cut the lesion, and 'not found' cases.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.preprocessing.lesion import detect_lesion, overlay   # noqa: E402

THUMB, COLS = 220, 6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--masks", default=None, help="folder of binary masks named <image_stem>.png (optional)")
    ap.add_argument("--out", default="reports/segmentation")
    a = ap.parse_args()

    files = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    rng = np.random.default_rng(a.seed)
    pick = [files[i] for i in rng.choice(len(files), min(a.n, len(files)), replace=False)]
    rows = (len(pick) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * THUMB, rows * (THUMB + 16)), "white")
    d = ImageDraw.Draw(sheet)
    scores, found = [], 0
    for i, p in enumerate(pick):
        with Image.open(p) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        les = detect_lesion(rgb)
        found += les.found
        t = ImageOps.contain(Image.fromarray(overlay(rgb, les, THUMB)), (THUMB - 4, THUMB - 4))
        x, y = (i % COLS) * THUMB, (i // COLS) * (THUMB + 16)
        sheet.paste(t, (x + 2, y + 2))
        label = f"{'area %.0f%%' % (les.area_fraction * 100) if les.found else 'NOT FOUND'}"
        if a.masks and (Path(a.masks) / f"{p.stem}.png").exists() and les.found:
            gt = np.asarray(Image.open(Path(a.masks) / f"{p.stem}.png").convert("L").resize(rgb.shape[1::-1])) > 127
            pr = les.mask > 0
            inter = (gt & pr).sum(); dice = 2 * inter / max(gt.sum() + pr.sum(), 1); iou = inter / max((gt | pr).sum(), 1)
            scores.append((dice, iou)); label += f" D{dice:.2f}"
        d.text((x + 4, y + THUMB), label, fill="black")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "lesion_detection_sample.png")
    print(f"Lesion located in {found}/{len(pick)} sampled photos. Sheet: {out / 'lesion_detection_sample.png'}")
    if scores:
        s = np.array(scores)
        print(f"Against masks: Dice {s[:, 0].mean():.3f}, IoU {s[:, 1].mean():.3f} (n={len(s)})")


if __name__ == "__main__":
    main()

