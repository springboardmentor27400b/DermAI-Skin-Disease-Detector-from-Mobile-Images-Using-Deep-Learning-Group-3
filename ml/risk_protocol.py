"""Fit the risk-category protocol (brief section 8) from a model's out-of-fold predictions. No thresholds are invented: they are read off data.

    python risk_protocol.py --runs runs/m2_sampler/convnext_tiny --target-sens 0.90 --high-spec 0.90 --out risk.json
    python export_model.py ... --risk risk.json          # or export_ensemble.py ... --risk risk.json

p_malignant = sum of the probabilities of BCC, SCC and MEL (all biopsy-confirmed skin cancers in PAD-UFES-20).
  t_low  : lower-quantile cut so that >= target-sens of malignant VALIDATION images have p_malignant >= t_low  -> below it = Low Risk
  t_high : cut so that >= high-spec of non-malignant VALIDATION images fall below it                           -> at/above = High Risk
Thresholds are fitted on the pooled validation predictions and then reported on the pooled test predictions of the same runs. Every image
is a validation image for one fold and a test image for another, so the test figures are slightly optimistic (two scalar thresholds only);
say so in the report. Requires Clinical Review is applied at inference time (lesion not found), not fitted here.
Folders need fold*/val_probs.csv and fold*/test_probs.csv (train.py writes them; ensemble.py writes them for ensembles).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from classes import class_order

CLASSES = class_order("pad-ufes-20")


def pooled(runs: Path, split: str, malignant: list[str]):
    parts = [pd.read_csv(f) for f in sorted(runs.glob(f"fold*/{split}_probs.csv"))]
    if not parts:
        raise SystemExit(f"No fold*/{split}_probs.csv under {runs}")
    df = pd.concat(parts, ignore_index=True)
    p_mal = df[[f"p_{c}" for c in malignant]].sum(axis=1).values
    y_mal = df.label_idx.map(lambda i: CLASSES[int(i)] in malignant).values
    return p_mal, y_mal


def fit(p_mal: np.ndarray, y_mal: np.ndarray, target_sens: float, high_spec: float) -> tuple[float, float]:
    t_low = float(np.quantile(p_mal[y_mal], 1 - target_sens, method="lower"))
    t_high = float(np.quantile(p_mal[~y_mal], high_spec, method="higher"))
    return t_low, max(t_high, t_low + 1e-6)


def summarise(p_mal, y_mal, t_low, t_high) -> dict:
    cat = np.where(p_mal >= t_high, "high", np.where(p_mal < t_low, "low", "moderate"))
    out = {"images": int(len(p_mal)), "malignant_images": int(y_mal.sum()),
           "sensitivity_not_low": float(((cat != "low") & y_mal).sum() / max(y_mal.sum(), 1)),
           "specificity_low": float(((cat == "low") & ~y_mal).sum() / max((~y_mal).sum(), 1)),
           "categories": {}}
    for k in ("low", "moderate", "high"):
        m = cat == k
        out["categories"][k] = {"share_of_images": float(m.mean()), "malignant_share": float(y_mal[m].mean()) if m.any() else None, "images": int(m.sum())}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="folder holding fold*/val_probs.csv and fold*/test_probs.csv")
    ap.add_argument("--malignant", nargs="+", default=["BCC", "SCC", "MEL"])
    ap.add_argument("--target-sens", type=float, default=0.90)
    ap.add_argument("--high-spec", type=float, default=0.90)
    ap.add_argument("--out", default="risk.json")
    a = ap.parse_args()
    for c in a.malignant:
        if c not in CLASSES:
            raise SystemExit(f"unknown class {c}; choose from {CLASSES}")
    runs = Path(a.runs)
    pv, yv = pooled(runs, "val", a.malignant)
    pt, yt = pooled(runs, "test", a.malignant)
    t_low, t_high = fit(pv, yv, a.target_sens, a.high_spec)
    perf_val, perf_test = summarise(pv, yv, t_low, t_high), summarise(pt, yt, t_low, t_high)
    protocol = {"protocol": f"dermai-risk-v1 (sens {a.target_sens:.2f}, spec {a.high_spec:.2f})", "malignant_classes": a.malignant,
                "target_sensitivity": a.target_sens, "high_specificity": a.high_spec, "t_low": round(t_low, 4), "t_high": round(t_high, 4),
                "fitted_on": f"pooled validation predictions, {perf_val['images']} images ({perf_val['malignant_images']} malignant), source {runs}",
                "performance": {"validation": perf_val, "test": perf_test}}
    Path(a.out).write_text(json.dumps(protocol, indent=2))
    print(f"t_low = {t_low:.3f}   t_high = {t_high:.3f}")
    for name, p in (("validation", perf_val), ("test", perf_test)):
        print(f"\n{name}: of the malignant images {p['sensitivity_not_low'] * 100:.1f}% are NOT labelled Low Risk; "
              f"{p['specificity_low'] * 100:.1f}% of non-malignant images are labelled Low Risk")
        for k, c in p["categories"].items():
            print(f"  {k:9s} {c['share_of_images'] * 100:5.1f}% of images, {('%.0f%%' % (c['malignant_share'] * 100)) if c['malignant_share'] is not None else '-':>4} malignant")
    print(f"\nwritten to {a.out}. A stricter --target-sens lowers t_low, so fewer images get Low Risk; set it with your supervisor and cite it as a research protocol.")


if __name__ == "__main__":
    main()

