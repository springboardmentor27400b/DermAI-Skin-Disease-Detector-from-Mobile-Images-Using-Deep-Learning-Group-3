"""Ensemble the models you already trained, from their saved predictions (no retraining, no GPU).

    python ensemble.py --out runs/m3_ens --members \
        convnext=runs/m2_sampler/convnext_tiny swin=runs/m3/swin_t densenet=runs/m2/densenet121

Each member folder must contain fold*/val_probs.csv and fold*/test_probs.csv (written by train.py; members must use the same
folds). Two ensembles are built per fold:
  ens_equal     plain average of the members' calibrated probabilities
  ens_weighted  weighted average; weights (step 0.1) are chosen on THAT FOLD'S VALIDATION predictions only (lowest log-loss)
                and then applied to its test predictions, so the test fold is never used to choose anything.
Prints pooled out-of-fold metrics for every member and both ensembles, and writes <out>/<name>/fold*/{val,test}_probs.csv
so compare_models.py can rank them (copy or symlink next to your other runs).
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

import metrics as M
from classes import class_order

CLASSES = class_order("pad-ufes-20")
PC = [f"p_{c}" for c in CLASSES]


def read(path: Path, fold: int, split: str) -> pd.DataFrame:
    f = path / f"fold{fold}" / f"{split}_probs.csv"
    if not f.exists():
        raise SystemExit(f"missing {f}")
    return pd.read_csv(f).set_index("image_id")


def simplex(n: int, steps: int = 10):
    """All weight vectors of length n made of multiples of 1/steps that sum to 1."""
    for c in itertools.product(range(steps + 1), repeat=n - 1):
        if sum(c) <= steps:
            yield np.array(list(c) + [steps - sum(c)], dtype=float) / steps


def nll(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1)).mean())


def stack(frames: list[pd.DataFrame]) -> np.ndarray:
    ids = frames[0].index
    for f in frames[1:]:
        if not ids.equals(f.index):
            if set(ids) != set(f.index):
                raise SystemExit("members were not evaluated on the same images; use the same folds file for every member.")
            frames[:] = [g.loc[ids] for g in frames]
    return np.stack([f[PC].values for f in frames])          # (members, images, classes)


def save(out: Path, name: str, fold: int, split: str, ref: pd.DataFrame, probs: np.ndarray) -> None:
    d = out / name / f"fold{fold}"
    d.mkdir(parents=True, exist_ok=True)
    df = ref[["group_id", "label_idx"]].copy()
    for i, c in enumerate(CLASSES):
        df[f"p_{c}"] = probs[:, i]
    df.reset_index().to_csv(d / f"{split}_probs.csv", index=False)
    (d / "metrics.json").write_text(json.dumps({"temperature": 1.0, "note": "ensemble of calibrated member probabilities"}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--members", nargs="+", required=True, help="name=run_folder, e.g. swin=runs/m3/swin_t")
    ap.add_argument("--out", default="runs/m3_ens")
    ap.add_argument("--folds", type=int, default=5)
    a = ap.parse_args()
    members = {}
    for m in a.members:
        name, _, path = m.partition("=")
        if not path:
            raise SystemExit(f"--members needs name=folder pairs, got {m!r}")
        members[name] = Path(path)
    names, out = list(members), Path(a.out)
    if len(names) < 2:
        raise SystemExit("Give at least two members.")

    pooled = {n: [] for n in names + ["ens_equal", "ens_weighted"]}
    weights_log = {}
    for k in range(a.folds):
        val = [read(members[n], k, "val") for n in names]
        test = [read(members[n], k, "test") for n in names]
        V, T = stack(val), stack(test)
        yv, yt = val[0].loc[val[0].index, "label_idx"].values, test[0]["label_idx"].values
        best_w, best = None, 1e9
        for w in simplex(len(names)):
            s = nll(np.tensordot(w, V, 1), yv)
            if s < best:
                best, best_w = s, w
        weights_log[k] = dict(zip(names, best_w.round(2).tolist()))
        eq = np.full(len(names), 1 / len(names))
        for i, n in enumerate(names):
            pooled[n].append(test[0].assign(**{c: T[i][:, j] for j, c in enumerate(PC)}))
        for name, w in (("ens_equal", eq), ("ens_weighted", best_w)):
            save(out, name, k, "val", val[0], np.tensordot(w, V, 1))
            save(out, name, k, "test", test[0], np.tensordot(w, T, 1))
            pooled[name].append(test[0].assign(**{c: np.tensordot(w, T, 1)[:, j] for j, c in enumerate(PC)}))
        print(f"fold {k}: val-chosen weights {weights_log[k]}")

    print("\nPooled out-of-fold test metrics (higher is better; ECE lower is better):")
    rows, evals = [], {}
    for n, parts in pooled.items():
        df = pd.concat(parts)
        r = M.compute(df.label_idx.values, df[PC].values, CLASSES)
        evals[n] = {"source": "pooled out-of-fold test predictions (patient-grouped 5-fold CV)", **r}
        rows.append({"model": n, "acc": r["accuracy"], "bal_acc": r["balanced_accuracy"], "macro_f1": r["macro_f1"], "auc": r["macro_auc_ovr"],
                     "ece": r["ece"], "SCC_f1": r["per_class"]["SCC"]["f1"], "MEL_recall": r["per_class"]["MEL"]["recall_sensitivity"],
                     "cancer_sens": r.get("malignant_vs_other", {}).get("sensitivity")})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("\nIf an ensemble's macro-F1 is within ~0.02 of the best single model it is not a reliable gain: run compare_models.py for bootstrap intervals.")
    (out / "weights_by_fold.json").write_text(json.dumps(weights_log, indent=2))
    (out / "evaluation.json").write_text(json.dumps(evals, indent=2))      # read by export_ensemble.py
    print(f"Ensemble predictions written to {out}/")


if __name__ == "__main__":
    main()

