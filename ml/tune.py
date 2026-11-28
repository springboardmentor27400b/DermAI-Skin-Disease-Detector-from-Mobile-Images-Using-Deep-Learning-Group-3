"""Random-search hyperparameter tuning for one architecture. Trials train on one fold and are ranked by VALIDATION macro-F1
(never the test fold), so the choice does not leak test information.

    python tune.py --arch efficientnet_b0 --folds data/splits_v2/folds.csv --cache data/pad_ufes_20/roi256 --out runs/tune --trials 12 --epochs 15
Writes tuning.csv and best_params.json; then train all folds with the winning flags:  python run_experiments.py ... -- <flags>
Resumable: finished trials are skipped.
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

import pandas as pd

SPACE = {
    "lr": [1e-4, 2e-4, 3e-4, 5e-4, 1e-3],
    "backbone-lr-mult": [0.03, 0.1, 0.3],
    "weight-decay": [1e-3, 1e-2, 5e-2],
    "imbalance": ["weighted_loss", "focal", "sampler"],
    "weight-power": [0.5, 0.75, 1.0],
    "label-smoothing": [0.0, 0.05, 0.1],
    "aug": ["basic", "strong"],
    "batch": [16, 32],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", required=True); ap.add_argument("--folds", required=True); ap.add_argument("--cache", required=True)
    ap.add_argument("--out", default="runs/tune"); ap.add_argument("--trials", type=int, default=12); ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--fold", type=int, default=0); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--dry-run", action="store_true")
    a, extra = ap.parse_known_args()
    extra = [e for e in extra if e != "--"]
    rng = random.Random(a.seed)
    out = Path(a.out) / a.arch; out.mkdir(parents=True, exist_ok=True)
    rows = []
    for t in range(a.trials):
        params = {k: rng.choice(v) for k, v in SPACE.items()}        # drawn every time so trial t is reproducible on resume
        d = out / f"trial{t:02d}"
        if not (d / "metrics.json").exists():
            cmd = [sys.executable, "train.py", "--arch", a.arch, "--folds", a.folds, "--fold", str(a.fold), "--cache", a.cache, "--out", str(d), "--epochs", str(a.epochs),
                   *[x for k, v in params.items() for x in (f"--{k}", str(v))], *extra]
            print(">>", " ".join(cmd))
            if a.dry_run:
                continue
            subprocess.run(cmd, check=True)
        m = json.loads((d / "metrics.json").read_text())["val"]
        rows.append({"trial": t, **params, "val_macro_f1": m["macro_f1"], "val_balanced_acc": m["balanced_accuracy"], "val_mel_recall": m["per_class"]["MEL"]["recall_sensitivity"]})
    if not rows:
        return
    df = pd.DataFrame(rows).sort_values("val_macro_f1", ascending=False)
    df.to_csv(out / "tuning.csv", index=False)
    best = df.iloc[0]
    (out / "best_params.json").write_text(json.dumps({k: (best[k].item() if hasattr(best[k], "item") else best[k]) for k in SPACE}, indent=2))
    print(df.round(3).to_string(index=False))
    print("\nBest flags:", " ".join(f"--{k} {best[k]}" for k in SPACE), "\nWith few melanoma patients per validation fold the ranking is noisy; prefer settings that win consistently.")


if __name__ == "__main__":
    main()

