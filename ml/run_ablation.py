"""Does the lesion crop help? Trains the same model on different crop recipes and compares them in one table.

    python run_ablation.py --images data/pad_ufes_20/images --folds data/splits_v2/folds.csv --existing-cache data/pad_ufes_20/roi256
Variants (same architecture, folds, epochs and imbalance method, only the crop differs):
  lesion  your existing cache (lesion ROI, minimum side 0.3 of the photo)
  wide    lesion ROI with minimum side 0.7 (stays close to the whole photo)
  centre  centre square crop, no lesion detection
Add --with-raw for a fourth variant: centre crop without the colour / contrast enhancement.
Resumable at every level: after a disconnect just run the same command again. Finished caches and folds are skipped, an interrupted
cache build continues from the last image, and an interrupted training run continues from its last epoch (last.pt). Results: reports/abl/comparison.md (+ charts).
"""
import argparse
import subprocess
import sys
from pathlib import Path


def preflight(images: str, folds: str) -> None:
    """Fail early (before any GPU time) if images named in the folds file are missing from the images folder."""
    import os
    import pandas as pd
    df = pd.read_csv(folds)
    col = "image_id" if "image_id" in df else "img_id"
    have = {Path(f).stem for f in os.listdir(images)}
    missing = sorted({i for i in df[col].astype(str) if Path(i).stem not in have})
    if missing:
        sys.exit(f"{len(missing)} image(s) listed in {folds} are not in {images}:\n  " + "\n  ".join(missing[:15]) +
                 "\nThey are probably missing from your upload (for example Google Drive did not finish syncing them). Copy them from the original dataset "
                 "into that folder, then run this command again; finished caches only add the new images.")
    print(f"Preflight OK: all {len(df)} images in the folds file are present.")


def run(cmd, dry):
    print(">>", " ".join(cmd))
    if not dry:
        subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True); ap.add_argument("--folds", required=True)
    ap.add_argument("--existing-cache", required=True, help="your current lesion-ROI cache (roi256)")
    ap.add_argument("--arch", default="convnext_tiny"); ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--only-folds", default="0,1"); ap.add_argument("--imbalance", default="sampler")
    ap.add_argument("--out", default="runs/abl"); ap.add_argument("--cache-root", default="data/pad_ufes_20")
    ap.add_argument("--workers", type=int, default=2, help="data-loader workers (Colab has 2 CPUs)")
    ap.add_argument("--variants", default="lesion,wide,centre", help="comma list to run, e.g. centre")
    ap.add_argument("--report-out", default="reports/abl")
    ap.add_argument("--with-raw", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    preflight(a.images, a.folds)
    root = Path(a.cache_root)
    variants = {
        "lesion": (Path(a.existing_cache), None),
        "wide": (root / "roi256_wide", ["--roi-min-frac", "0.7"]),
        "centre": (root / "roi256_centre", ["--no-lesion"]),
    }
    if a.with_raw:
        variants["centre_raw"] = (root / "roi256_centre_raw", ["--no-lesion", "--no-enhance"])
    wanted = [v for v in a.variants.split(",") if v]
    unknown = [v for v in wanted if v not in variants]
    if unknown:
        raise SystemExit(f"unknown variants {unknown}; choose from {list(variants)}")
    for name, (cache, flags) in ((n, variants[n]) for n in wanted):
        if flags:                                          # no-op for a finished cache, continues a partial one
            run([sys.executable, "precompute_rois.py", "--images", a.images, "--out", str(cache), *flags], a.dry_run)
        for k in a.only_folds.split(","):
            out = Path(a.out) / name / f"fold{k}"
            if (out / "metrics.json").exists():
                print(f"skip {name} fold{k} (done)"); continue
            run([sys.executable, "train.py", "--arch", a.arch, "--folds", a.folds, "--fold", k, "--cache", str(cache), "--out", str(out),
                 "--epochs", str(a.epochs), "--imbalance", a.imbalance, "--workers", str(a.workers), "--resume"], a.dry_run)
    run([sys.executable, "compare_models.py", "--runs", a.out, "--out", a.report_out, "--bootstrap", "500"], a.dry_run)


if __name__ == "__main__":
    main()

