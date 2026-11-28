"""Which preprocessing recipe produced your cached crops? Compares cached crops with freshly computed ones.

    python check_pipeline_consistency.py --images data/pad_ufes_20/images --cache data/pad_ufes_20/roi256 --n 12

Prints the mean absolute pixel difference for each recipe (hair removal on/off, lesion ROI on/off, enhancement on/off). The
matching recipe has a difference near 0. If it is not the one the API uses (see the model's meta.json "preprocessing"), edit
that field, e.g.  "size=256 enhance=True lesion_roi=True hair_removal=False"; the API follows meta.json automatically.
"""
import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.preprocessing.lesion import detect_lesion   # noqa: E402
from app.preprocessing.pipeline import preprocess     # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True); ap.add_argument("--cache", required=True)
    ap.add_argument("--size", type=int, default=256); ap.add_argument("--n", type=int, default=12); ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    cache = Path(a.cache)
    files = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg") and (cache / f"{p.stem}.png").exists())
    pick = [files[i] for i in np.random.default_rng(a.seed).choice(len(files), min(a.n, len(files)), replace=False)]
    recipes = list(itertools.product([True, False], repeat=3))        # hair, lesion_roi, enhance
    err = {r: [] for r in recipes}
    for p in pick:
        with Image.open(p) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        cached = np.asarray(Image.open(cache / f"{p.stem}.png").convert("RGB")).astype(float)
        les = detect_lesion(rgb)
        for hair, roi, enh in recipes:
            out = preprocess(rgb, a.size, lesion=les if roi else None, enhance=enh, remove_hair_artifacts=hair).preview_rgb
            err[(hair, roi, enh)].append(float(np.abs(out.astype(float) - cached).mean()) if out.shape == cached.shape else 255.0)
    print(f"Mean absolute pixel difference vs cached crops ({len(pick)} images); the recipe near 0 produced your cache:\n")
    for r, v in sorted(err.items(), key=lambda kv: np.mean(kv[1])):
        print(f"  hair_removal={r[0]!s:5} lesion_roi={r[1]!s:5} enhance={r[2]!s:5}  diff {np.mean(v):7.3f}")


if __name__ == "__main__":
    main()

