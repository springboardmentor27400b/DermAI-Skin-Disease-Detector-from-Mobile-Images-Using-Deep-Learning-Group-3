"""Exploratory data analysis for PAD-UFES-20 (default) or HAM10000.

    python eda.py --dataset pad_ufes_20 --metadata data/pad_ufes_20/metadata.csv \
                  --images data/pad_ufes_20/images --out reports/eda --verify-images

Writes summary.json and charts to --out. Covers class distribution and imbalance, patients / lesions / images,
demographics, body sites, skin tone (Fitzpatrick), label reliability (biopsy), missing values, and an image
integrity check (files listed but missing, files present but unlisted, unreadable files, size and brightness).
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from datasets import IMAGE_EXTS, SPECS, load, resolve_image

ACCENT = "#26786B"


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)


def bar(series: pd.Series, title: str, path: Path, horizontal=False):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    (series.plot.barh if horizontal else series.plot.bar)(ax=ax, color=ACCENT)
    _style(ax, title)
    for c in ax.containers:
        ax.bar_label(c, fontsize=8, padding=2)
    if not horizontal:
        plt.setp(ax.get_xticklabels(), rotation=0)
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


def integrity(df: pd.DataFrame, images: Path, verify: bool, sample: int, seed: int) -> dict:
    from PIL import Image
    listed = {}
    for iid in df.image_id.dropna():
        listed[iid] = resolve_image(images, iid)
    missing = sorted(k for k, v in listed.items() if v is None)
    present_files = {p.name for p in images.iterdir() if p.suffix.lower() in IMAGE_EXTS}
    listed_names = {v.name for v in listed.values() if v is not None}
    out = {"images_dir": str(images), "files_in_folder": len(present_files), "metadata_rows": int(len(df)),
           "listed_but_missing": len(missing), "listed_but_missing_examples": missing[:10],
           "in_folder_but_unlisted": len(present_files - listed_names), "duplicate_image_ids": int(df.image_id.duplicated().sum())}
    paths = [v for v in listed.values() if v is not None]
    rng = np.random.default_rng(seed)
    check = paths if verify else [paths[i] for i in rng.choice(len(paths), min(sample, len(paths)), replace=False)] if paths else []
    bad, rows = [], []
    for p in check:
        try:
            with Image.open(p) as im:
                im.verify()
            with Image.open(p) as im:
                g = np.asarray(im.convert("L"))
                rows.append(dict(w=im.width, h=im.height, brightness=float(g.mean()), contrast=float(g.std())))
        except Exception:
            bad.append(p.name)
    out["images_checked"] = len(check)
    out["unreadable"] = len(bad); out["unreadable_examples"] = bad[:10]
    if rows:
        s = pd.DataFrame(rows)
        out["size_px"] = {"min_w": int(s.w.min()), "median_w": int(s.w.median()), "max_w": int(s.w.max()),
                          "min_h": int(s.h.min()), "median_h": int(s.h.median()), "max_h": int(s.h.max())}
        out["common_sizes"] = {f"{w}x{h}": int(n) for (w, h), n in s.groupby(["w", "h"]).size().sort_values(ascending=False).head(3).items()}
        out["brightness_mean"] = round(s.brightness.mean(), 1); out["contrast_mean"] = round(s.contrast.mean(), 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(SPECS), default="pad_ufes_20")
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--images", default=None, help="folder with all images (optional but recommended)")
    ap.add_argument("--out", default="reports/eda")
    ap.add_argument("--verify-images", action="store_true", help="open every image (slower); default samples 300")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    spec = SPECS[a.dataset]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    df = load(spec, a.metadata)
    unknown = df.attrs["unknown_labels"]
    if unknown:
        print(f"WARNING: labels not in the class list (excluded from class counts): {unknown}")
    labelled = df.dropna(subset=["label"])
    order = [c for c in spec.classes]
    counts = labelled.label.value_counts().reindex(order).fillna(0).astype(int)
    nonzero = counts[counts > 0]
    per_group = df.groupby("group_id").size()

    summary = {
        "dataset": spec.title, "images": int(len(df)), "patients": int(df.patient_id.nunique()) if df.patient_id.notna().any() else None,
        "lesions": int(df.lesion_id.nunique()) if df.lesion_id.notna().any() else None,
        "split_group": "patient_id" if spec.patient_col else "lesion_id",
        "images_per_group": {"min": int(per_group.min()), "median": float(per_group.median()), "max": int(per_group.max()),
                             "groups_with_more_than_one_image": int((per_group > 1).sum())},
        "class_counts": counts.to_dict(),
        "class_names": spec.classes,
        "class_share_pct": (counts / counts.sum() * 100).round(2).to_dict(),
        "imbalance_ratio_max_to_min": round(float(nonzero.max() / nonzero.min()), 1),
        "rows_without_valid_label": int(df.label.isna().sum()),
        "missing_values_pct": {c: round(float(v), 1) for c, v in (df.isna().mean() * 100).items() if v > 0 and c in ("age", "sex", "site", "fitzpatrick", "biopsied")},
    }
    if "age" in df:
        summary["age"] = {k: round(float(v), 1) for k, v in df.age.describe()[["mean", "50%", "min", "max"]].items()}
        summary["median_age_by_class"] = labelled.groupby("label").age.median().round(1).dropna().to_dict()
    if "sex" in df:
        summary["sex_counts"] = df.sex.value_counts().to_dict()
    if "fitzpatrick" in df:
        summary["fitzpatrick_counts"] = df.fitzpatrick.value_counts().sort_index().to_dict()
    if "biopsied" in df:
        summary["biopsy_confirmed_pct_by_class"] = (labelled.groupby("label").biopsied.apply(lambda s: round(float((s == True).mean() * 100), 1))).to_dict()  # noqa: E712

    if df.patient_id.notna().any():
        summary["patients_with_multiple_diagnoses"] = int((labelled.groupby("patient_id").label.nunique() > 1).sum())

    # Inverse-frequency weights: starting point for weighted / focal loss in Milestone 2.
    w = counts.sum() / (len(counts) * counts.clip(lower=1))
    summary["suggested_class_weights"] = (w / w.mean()).round(3).to_dict()
    # With few patients per class a fixed split is unreliable. Flag it so the report can justify cross-validation.
    patients_per_class = labelled.groupby("label").group_id.nunique().reindex(order).fillna(0).astype(int)
    summary["groups_per_class"] = patients_per_class.to_dict()
    summary["rare_classes_under_30_groups"] = [c for c, n in patients_per_class.items() if n < 30]

    if a.images:
        images = Path(a.images)
        if not images.is_dir():
            raise SystemExit(f"--images folder not found: {images}")
        summary["integrity"] = integrity(df, images, a.verify_images, 300, a.seed)

    bar(counts, "Class distribution (images)", out / "class_distribution.png")
    bar(patients_per_class, "Independent groups per class (patients)", out / "groups_per_class.png")
    if df.age.notna().any() if "age" in df else False:
        fig, ax = plt.subplots(figsize=(7.5, 4.2)); df.age.dropna().plot.hist(bins=20, ax=ax, color=ACCENT); _style(ax, "Age distribution")
        fig.tight_layout(); fig.savefig(out / "age_distribution.png", dpi=140); plt.close(fig)
    if "site" in df:
        bar(df.site.value_counts().sort_values(), "Body site", out / "body_site.png", horizontal=True)
    if "fitzpatrick" in df and df.fitzpatrick.notna().any():
        bar(df.fitzpatrick.value_counts().sort_index(), "Fitzpatrick skin type (as recorded)", out / "fitzpatrick.png")
    if "biopsied" in df and df.biopsied.notna().any():
        share = pd.Series(summary["biopsy_confirmed_pct_by_class"]).reindex(order)
        bar(share, "Biopsy-confirmed share by class (%)", out / "biopsy_by_class.png")
    if "sex" in df:
        ct = pd.crosstab(labelled.label, labelled.sex).reindex(order)
        ax = ct.plot.bar(stacked=True, figsize=(7.5, 4.2), colormap="GnBu"); _style(ax, "Class by sex"); plt.setp(ax.get_xticklabels(), rotation=0)
        plt.tight_layout(); plt.savefig(out / "class_by_sex.png", dpi=140); plt.close()
    fig, ax = plt.subplots(figsize=(7.5, 4.2)); per_group.value_counts().sort_index().plot.bar(ax=ax, color=ACCENT)
    _style(ax, f"Images per {summary['split_group']}"); plt.setp(ax.get_xticklabels(), rotation=0)
    fig.tight_layout(); fig.savefig(out / "images_per_group.png", dpi=140); plt.close(fig)

    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    keys = ["dataset", "images", "patients", "lesions", "class_counts", "imbalance_ratio_max_to_min", "groups_per_class", "rare_classes_under_30_groups", "missing_values_pct"]
    print(json.dumps({k: summary[k] for k in keys if k in summary}, indent=2, default=str))
    if "integrity" in summary:
        print("\nImage integrity:", json.dumps({k: v for k, v in summary["integrity"].items() if "examples" not in k or v}, indent=2))
    print(f"\nFull report and charts: {out}/")


if __name__ == "__main__":
    main()

