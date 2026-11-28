"""How good is lesion detection? Scores the old colour detector against your masks and, optionally, the trained U-Net.

    python compare_detectors.py --images data/to_annotate --masks data/masks --unet-cv runs/seg/unet_cv/cv_scores.csv
Every annotated photo is scored by the colour detector (it needs no training, so all photos are test photos). A photo where the
detector finds nothing scores Dice 0. The U-Net numbers come from cross-validation, so each photo was scored by a model that
never saw it. Both are scored at 256 px on the same photos; the table also gives a paired 95% interval for the difference.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.preprocessing.lesion import detect_lesion   # noqa: E402
from seg_metrics import seg_scores                      # noqa: E402

S = 256


def ci(v, n=2000, seed=0):
    r = np.random.default_rng(seed); v = np.asarray(v, float)
    m = [r.choice(v, len(v)).mean() for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True); ap.add_argument("--masks", required=True)
    ap.add_argument("--unet-cv", default=None, help="cv_scores.csv from train_seg.py --cv")
    ap.add_argument("--out", default="reports/segmentation")
    a = ap.parse_args()
    imgs = {p.stem: p for p in Path(a.images).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")}
    rows = []
    for m in sorted(Path(a.masks).glob("*.png")):
        if m.stem not in imgs:
            continue
        with Image.open(imgs[m.stem]) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        gt = cv2.resize((cv2.imread(str(m), cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8), (S, S), interpolation=cv2.INTER_NEAREST)
        les = detect_lesion(rgb)
        pr = cv2.resize(les.mask, (S, S), interpolation=cv2.INTER_NEAREST) if les.found and les.mask is not None else np.zeros((S, S), np.uint8)
        rows.append({"image": imgs[m.stem].name, "found": bool(les.found), **seg_scores(pr, gt)})
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No image/mask pairs found.")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "colour_detector_scores.csv", index=False)
    lo, hi = ci(df.dice)
    res = {"colour_detector": {"images": len(df), "found_rate": float(df.found.mean()), "dice": float(df.dice.mean()), "dice_ci95": [lo, hi],
                               "dice_when_found": float(df[df.found].dice.mean()) if df.found.any() else None, "iou": float(df.iou.mean()),
                               "dice_below_0.5": int((df.dice < 0.5).sum())}}
    print(f"COLOUR DETECTOR on {len(df)} annotated photos: found {df.found.mean() * 100:.0f}%, Dice {df.dice.mean():.3f} (95% CI {lo:.3f}-{hi:.3f}), "
          f"Dice when found {res['colour_detector']['dice_when_found']}, {res['colour_detector']['dice_below_0.5']} photos below Dice 0.5")
    if a.unet_cv:
        u = pd.read_csv(a.unet_cv)
        j = df.merge(u, on="image", suffixes=("_colour", "_unet"))
        d = (j.dice_unet - j.dice_colour).values
        dlo, dhi = ci(d)
        ulo, uhi = ci(j.dice_unet)
        res["unet_cv"] = {"images": len(j), "dice": float(j.dice_unet.mean()), "dice_ci95": [ulo, uhi], "iou": float(j.iou_unet.mean()), "dice_below_0.5": int((j.dice_unet < 0.5).sum())}
        res["paired_difference_dice_unet_minus_colour"] = {"mean": float(d.mean()), "ci95": [dlo, dhi], "unet_better_on": int((d > 0).sum()), "of": len(d)}
        print(f"U-NET (cross-validated) on the same {len(j)} photos: Dice {j.dice_unet.mean():.3f} (95% CI {ulo:.3f}-{uhi:.3f}), IoU {j.iou_unet.mean():.3f}, {res['unet_cv']['dice_below_0.5']} below Dice 0.5")
        print(f"Difference (U-Net minus colour): {d.mean():+.3f} Dice, paired 95% CI {dlo:+.3f} to {dhi:+.3f}; U-Net better on {int((d > 0).sum())} of {len(d)} photos")
    (out / "detector_comparison.json").write_text(json.dumps(res, indent=2))
    print(f"saved to {out}/")


if __name__ == "__main__":
    main()

