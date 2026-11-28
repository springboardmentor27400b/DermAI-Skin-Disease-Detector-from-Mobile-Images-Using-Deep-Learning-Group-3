"""Create patient-grouped, class-stratified splits.

PAD-UFES-20 has several photos per patient and per lesion. A random image-level split would put the same
patient in train and test and inflate every metric, so all images of one patient stay together.

    python prepare_dataset.py --dataset pad_ufes_20 --metadata data/pad_ufes_20/metadata.csv \
           --images data/pad_ufes_20/images --out data/splits            # train / val / test
    python prepare_dataset.py ... --kfold 5                               # also writes folds.csv for cross-validation

The dataset is small and some classes are rare (for example melanoma), so a fixed split can leave a class almost
empty in val/test. Use the k-fold file for reported results; the printed warnings tell you when that applies.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from datasets import SPECS, load, resolve_image


def carve(frame: pd.DataFrame, frac: float, seed: int):
    n = max(2, round(1 / frac))
    rest, held = next(StratifiedGroupKFold(n_splits=n, shuffle=True, random_state=seed).split(frame, frame.label, groups=frame.group_id))
    return frame.iloc[rest], frame.iloc[held]


def assert_disjoint(parts: dict[str, pd.DataFrame]) -> None:
    names = list(parts)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = set(parts[a].group_id) & set(parts[b].group_id)
            assert not both, f"group leakage between {a} and {b}: {sorted(both)[:5]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(SPECS), default="pad_ufes_20")
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--images", default=None)
    ap.add_argument("--out", default="data/splits")
    ap.add_argument("--test", type=float, default=0.15)
    ap.add_argument("--val", type=float, default=0.15)
    ap.add_argument("--kfold", type=int, default=0, help="also write folds.csv with this many folds")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true", help="overwrite existing split files")
    a = ap.parse_args()

    spec = SPECS[a.dataset]
    df = load(spec, a.metadata)
    bad = df[df.label.isna()]
    if len(bad):
        print(f"WARNING: dropping {len(bad)} rows without a valid label (unknown: {df.attrs['unknown_labels']})")
    df = df.dropna(subset=["label", "group_id"]).copy()
    if a.images:
        folder = Path(a.images)
        df["image_path"] = df.image_id.map(lambda i: (lambda p: p.name if p else None)(resolve_image(folder, i)))
        gone = df.image_path.isna().sum()
        if gone:
            print(f"WARNING: dropping {gone} rows whose image file is not in {folder}")
        df = df.dropna(subset=["image_path"])
    classes = list(spec.classes)
    df["label_idx"] = df.label.map({c: i for i, c in enumerate(classes)})

    trainval, test = carve(df, a.test, a.seed)
    train, val = carve(trainval, a.val / (1 - a.test), a.seed)
    parts = {"train": train, "val": val, "test": test}
    assert_disjoint(parts)

    out = Path(a.out)
    if (out / "train.csv").exists() and not a.force:
        raise SystemExit(f"{out}/train.csv already exists. Choose another --out, or pass --force to overwrite it.")
    out.mkdir(parents=True, exist_ok=True)
    report = {"dataset": spec.title, "seed": a.seed, "group_column": "patient_id" if spec.patient_col else "lesion_id", "classes": classes}
    for name, part in parts.items():
        part.to_csv(out / f"{name}.csv", index=False)
        counts = part.label.value_counts().reindex(classes).fillna(0).astype(int).to_dict()
        report[name] = {"images": len(part), "groups": int(part.group_id.nunique()), "class_counts": counts}
        thin = [c for c, n in counts.items() if n < 5]
        if thin and name != "train":
            print(f"WARNING: {name} has fewer than 5 images of {thin}. Metrics for those classes will be unreliable; use --kfold.")
    (out / "class_to_idx.json").write_text(json.dumps({c: i for i, c in enumerate(classes)}, indent=2))

    if a.kfold:
        folded = df.copy(); folded["fold"] = -1
        for k, (_, idx) in enumerate(StratifiedGroupKFold(n_splits=a.kfold, shuffle=True, random_state=a.seed).split(folded, folded.label, groups=folded.group_id)):
            folded.iloc[idx, folded.columns.get_loc("fold")] = k
        assert (folded.groupby("group_id").fold.nunique() == 1).all(), "a group landed in more than one fold"
        folded.to_csv(out / "folds.csv", index=False)
        report["folds"] = {int(k): g.label.value_counts().reindex(classes).fillna(0).astype(int).to_dict() for k, g in folded.groupby("fold")}

    (out / "split_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("dataset", "group_column", "train", "val", "test")}, indent=2))
    print(f"\nSplits written to {out}/")


if __name__ == "__main__":
    main()

