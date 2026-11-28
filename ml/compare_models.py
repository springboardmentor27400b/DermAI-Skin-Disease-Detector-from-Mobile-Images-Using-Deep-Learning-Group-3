"""Compare every trained architecture and pick the best baseline.

    python compare_models.py --runs runs/m2 --out reports/m2 --bootstrap 1000

Expects runs/<name>/<arch>/fold<k>/test_probs.csv. Predictions from all folds are pooled (each image is predicted once, by
a model that never saw its patient), metrics are computed on the pooled set and per fold (mean +- std), and a patient-level
bootstrap gives a 95% interval for macro-F1. Selection: highest pooled macro-F1 (balanced accuracy breaks ties).
Writes comparison.csv / .md / .json, comparison charts, one confusion matrix per model and best_baseline.json.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import metrics as M
from classes import class_order

CLASSES = class_order("pad-ufes-20")


def load_arch(d: Path):
    parts = [pd.read_csv(f).assign(fold=int(f.parent.name.replace("fold", ""))) for f in sorted(d.glob("fold*/test_probs.csv"))]
    return pd.concat(parts, ignore_index=True) if parts else None


def arrays(df):
    return df.label_idx.values, df[[f"p_{c}" for c in CLASSES]].values


def bootstrap_f1(df, n, seed=0):
    rng = np.random.default_rng(seed)
    groups = {g: x for g, x in df.groupby("group_id")}
    keys = np.array(list(groups))
    vals = []
    for _ in range(n):
        s = pd.concat([groups[k] for k in rng.choice(keys, len(keys))])
        y, p = arrays(s)
        vals.append(M.compute(y, p, CLASSES)["macro_f1"])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", default="reports/m2")
    ap.add_argument("--bootstrap", type=int, default=500)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    rows, full = [], {}
    for d in sorted(p for p in Path(a.runs).iterdir() if p.is_dir()):
        df = load_arch(d)
        if df is None:
            continue
        y, p = arrays(df)
        pooled = M.compute(y, p, CLASSES)
        per_fold = [M.compute(*arrays(g), CLASSES) for _, g in df.groupby("fold")]
        f1s = [m["macro_f1"] for m in per_fold]; bas = [m["balanced_accuracy"] for m in per_fold]
        lo, hi = bootstrap_f1(df, a.bootstrap) if a.bootstrap else (float("nan"),) * 2
        temps = [json.loads(f.read_text()).get("temperature") for f in sorted(d.glob("fold*/metrics.json"))]
        rows.append({"model": d.name, "folds": df.fold.nunique(), "images": len(df), "accuracy": pooled["accuracy"],
                     "balanced_acc": pooled["balanced_accuracy"], "macro_f1": pooled["macro_f1"], "macro_f1_ci_low": lo, "macro_f1_ci_high": hi,
                     "macro_f1_fold_mean": np.mean(f1s), "macro_f1_fold_std": np.std(f1s), "balanced_acc_fold_std": np.std(bas),
                     "macro_auc": pooled["macro_auc_ovr"], "mcc": pooled["mcc"], "ece": pooled["ece"],
                     "mel_recall": pooled["per_class"]["MEL"]["recall_sensitivity"],
                     "cancer_sensitivity": pooled.get("malignant_vs_other", {}).get("sensitivity"),
                     "cancer_specificity": pooled.get("malignant_vs_other", {}).get("specificity"),
                     "mean_temperature": float(np.mean([t for t in temps if t]))})
        full[d.name] = pooled
    if not rows:
        raise SystemExit(f"No fold*/test_probs.csv found under {a.runs}")
    tab = pd.DataFrame(rows).sort_values(["macro_f1", "balanced_acc"], ascending=False).reset_index(drop=True)
    tab.to_csv(out / "comparison.csv", index=False)
    (out / "comparison.json").write_text(json.dumps(full, indent=2))

    show = tab[["model", "folds", "accuracy", "balanced_acc", "macro_f1", "macro_f1_ci_low", "macro_f1_ci_high", "macro_auc", "mcc", "ece", "mel_recall", "cancer_sensitivity"]].round(3)
    cols = list(show.columns)
    md = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "\n".join("| " + " | ".join(str(v) for v in r) + " |" for r in show.values)
    (out / "comparison.md").write_text(md + "\n")
    print(md)

    best = tab.iloc[0]
    (out / "best_baseline.json").write_text(json.dumps({"model": best.model, "selected_by": "pooled macro-F1 (balanced accuracy breaks ties)",
                                                        **{k: float(best[k]) for k in ("macro_f1", "balanced_acc", "macro_auc", "mel_recall")}}, indent=2))
    print(f"\nBest baseline: {best.model} (macro-F1 {best.macro_f1:.3f}, 95% CI {best.macro_f1_ci_low:.3f}-{best.macro_f1_ci_high:.3f}). "
          f"If intervals overlap, the ranking between those models is not statistically reliable.")

    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(tab)); w = .38
    ax.bar(x - w / 2, tab.macro_f1, w, label="macro-F1", color="#26786B"); ax.bar(x + w / 2, tab.balanced_acc, w, label="balanced accuracy", color="#9CC9BF")
    ax.errorbar(x - w / 2, tab.macro_f1, yerr=[tab.macro_f1 - tab.macro_f1_ci_low, tab.macro_f1_ci_high - tab.macro_f1], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x); ax.set_xticklabels(tab.model, rotation=20, ha="right"); ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=2, frameon=False); ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Model comparison (pooled out-of-fold, 95% CI on macro-F1)", loc="left", fontsize=10, fontweight="bold")
    fig.tight_layout(); fig.savefig(out / "model_comparison.png", dpi=140, bbox_inches="tight"); plt.close(fig)

    f1 = pd.DataFrame({m: [full[m]["per_class"][c]["f1"] for c in CLASSES] for m in tab.model}, index=CLASSES)
    fig, ax = plt.subplots(figsize=(1.2 * len(tab) + 2, 4)); im = ax.imshow(f1.values, vmin=0, vmax=1, cmap="GnBu", aspect="auto")
    ax.set_xticks(range(len(f1.columns))); ax.set_xticklabels(f1.columns, rotation=20, ha="right"); ax.set_yticks(range(len(CLASSES))); ax.set_yticklabels(CLASSES)
    for i in range(f1.shape[0]):
        for j in range(f1.shape[1]):
            ax.text(j, i, f"{f1.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Per-class F1", loc="left", fontsize=10, fontweight="bold"); fig.colorbar(im); fig.tight_layout(); fig.savefig(out / "per_class_f1.png", dpi=140, bbox_inches="tight"); plt.close(fig)

    for m in tab.model:
        cm = np.array(full[m]["confusion_matrix"]); norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
        fig, ax = plt.subplots(figsize=(5, 4.4)); ax.imshow(norm, cmap="GnBu", vmin=0, vmax=1)
        ax.set_xticks(range(len(CLASSES))); ax.set_xticklabels(CLASSES); ax.set_yticks(range(len(CLASSES))); ax.set_yticklabels(CLASSES)
        ax.set_xlabel("predicted"); ax.set_ylabel("true")
        for i in range(len(CLASSES)):
            for j in range(len(CLASSES)):
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=8, color="white" if norm[i, j] > .6 else "black")
        ax.set_title(f"{m}: confusion matrix (counts, rows normalised)", loc="left", fontsize=9, fontweight="bold")
        fig.tight_layout(); fig.savefig(out / f"confusion_{m}.png", dpi=130); plt.close(fig)
    print(f"Charts and tables in {out}/")


if __name__ == "__main__":
    main()

