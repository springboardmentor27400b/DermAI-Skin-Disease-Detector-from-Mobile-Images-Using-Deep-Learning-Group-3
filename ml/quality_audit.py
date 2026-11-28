"""Run the app's image-quality check (backend/app/preprocessing/quality.py) over a whole image folder.

    python quality_audit.py --images data/pad_ufes_20/images --metadata data/pad_ufes_20/metadata.csv --out reports/quality

Shows how the current thresholds treat the real dataset: the share rated good / acceptable / poor, which issues
are flagged most, the per-class split, and the metric distributions with the thresholds drawn on them.
Writes quality_scores.csv (one row per image) for threshold calibration in Milestone 2.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.core.config import settings                      # noqa: E402
from app.preprocessing import quality as q                 # noqa: E402
from datasets import IMAGE_EXTS, SPECS, load               # noqa: E402

ACCENT = "#26786B"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--metadata", default=None, help="adds a per-class breakdown")
    ap.add_argument("--dataset", choices=sorted(SPECS), default="pad_ufes_20")
    ap.add_argument("--out", default="reports/quality")
    a = ap.parse_args()

    folder = Path(a.images)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not files:
        raise SystemExit(f"No images found in {folder.resolve()}")
    rows = []
    for i, p in enumerate(files, 1):
        with Image.open(p) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        r = q.assess_quality(rgb)
        rows.append(dict(file=p.name, short_side=min(rgb.shape[:2]), label=r.label, blur=r.blur_score,
                         brightness=r.brightness, contrast=r.contrast, issues=" | ".join(r.issues)))
        if i % 500 == 0:
            print(f"  {i}/{len(files)}")
    df = pd.DataFrame(rows)

    if a.metadata:
        meta = load(SPECS[a.dataset], a.metadata)[["image_id", "label"]].rename(columns={"label": "diagnosis"})
        df = df.merge(meta, left_on="file", right_on="image_id", how="left").drop(columns="image_id")

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "quality_scores.csv", index=False)

    n = len(df)
    pct = lambda s: round(float(s.mean() * 100), 1)
    flag = lambda text: pct(df.issues.str.contains(text, regex=False))
    summary = {
        "images": n,
        "rating_pct": (df.label.value_counts(normalize=True).reindex(["good", "acceptable", "poor"]).fillna(0) * 100).round(1).to_dict(),
        "issue_pct": {"blurred (poor)": flag("is blurred"), "slightly soft": flag("slightly soft"), "too dark": flag("too dark"), "dim lighting": flag("dim"),
                      "overexposed": flag("overexposed"), "bright": flag("is bright"), "very low contrast (poor)": flag("Very low contrast"),
                      "low contrast": flag("Low contrast."), "blank borders": flag("blank borders"),
                      "not mostly skin": flag("not skin"), "possible occlusion": flag("covering part"), "hair noticeable": flag("Hair covers")},
        "shorter_side_under_upload_minimum_pct": pct(df.short_side < settings.min_resolution),
        "shorter_side_under_upload_minimum_count": int((df.short_side < settings.min_resolution).sum()),
        "upload_minimum_px": settings.min_resolution,
        "percentiles": {m: df[m].quantile([.05, .25, .5, .75, .95]).round(1).to_dict() for m in ("blur", "brightness", "contrast")},
        "thresholds": {"blur": [q.BLUR_POOR, q.BLUR_ACCEPTABLE], "brightness_dark": [q.DARK_POOR, q.DARK_ACCEPTABLE],
                       "brightness_bright": [q.BRIGHT_ACCEPTABLE, q.BRIGHT_POOR], "contrast": [q.CONTRAST_POOR, q.CONTRAST_ACCEPTABLE]},
    }
    if "diagnosis" in df:
        summary["rating_pct_by_class"] = {c: (g.label.value_counts(normalize=True).reindex(["good", "acceptable", "poor"]).fillna(0) * 100).round(1).to_dict()
                                          for c, g in df.dropna(subset=["diagnosis"]).groupby("diagnosis")}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    marks = {"blur": [q.BLUR_POOR, q.BLUR_ACCEPTABLE], "brightness": [q.DARK_POOR, q.DARK_ACCEPTABLE, q.BRIGHT_ACCEPTABLE, q.BRIGHT_POOR], "contrast": [q.CONTRAST_POOR, q.CONTRAST_ACCEPTABLE]}
    for ax, m in zip(axes, marks):
        data = df[m].clip(upper=df[m].quantile(.99))
        ax.hist(data, bins=40, color=ACCENT)
        for t in marks[m]:
            ax.axvline(t, color="#B3261E", lw=1.2, ls="--")
        ax.set_title(f"{m} (dashed = thresholds)", loc="left", fontsize=10, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "quality_distributions.png", dpi=140); plt.close(fig)

    print(json.dumps({k: summary[k] for k in ("images", "rating_pct", "issue_pct", "shorter_side_under_upload_minimum_count", "percentiles")}, indent=2))
    print(f"\nPer-image scores, summary.json and chart: {out}/")


if __name__ == "__main__":
    main()

