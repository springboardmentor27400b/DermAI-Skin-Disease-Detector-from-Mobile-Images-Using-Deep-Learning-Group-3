"""Image-quality metrics from the brief (section 9) against your own labels.

1. Label a sample: edit reports/quality/quality_scores.csv-style file `labels.csv` with columns  file, label  (good|acceptable|poor)
   and optionally  blurred (0/1).  Eyeballing 150-300 photos from the review sheets is enough.
2. python quality_eval.py --scores reports/quality/quality_scores.csv --labels labels.csv

Reports: quality-classification accuracy and confusion, image rejection rate, acceptable-image percentage, poor-image detection
rate (recall of 'poor'), and blur-detection accuracy when a blurred column exists. Use it to choose the thresholds in
docs/quality_thresholds.md instead of percentiles.
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

ORDER = ["good", "acceptable", "poor"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True); ap.add_argument("--labels", required=True); ap.add_argument("--blur-threshold", type=float, default=None)
    a = ap.parse_args()
    s, l = pd.read_csv(a.scores), pd.read_csv(a.labels)
    df = s.merge(l[[c for c in ("file", "label", "blurred") if c in l]], on="file", suffixes=("_pred", "_true"))
    if df.empty:
        raise SystemExit("No overlap between scores and labels (match the 'file' column).")
    y, p = df.label_true, df.label_pred
    cm = confusion_matrix(y, p, labels=ORDER)
    out = {"n_labelled": len(df), "quality_classification_accuracy": float((y == p).mean()),
           "confusion_true_rows_pred_cols": {"order": ORDER, "matrix": cm.tolist()},
           "image_rejection_rate_pct": float((p == "poor").mean() * 100), "acceptable_image_pct": float((p != "poor").mean() * 100),
           "poor_image_detection_rate": float(((y == "poor") & (p == "poor")).sum() / max((y == "poor").sum(), 1)),
           "false_rejection_rate": float(((y != "poor") & (p == "poor")).sum() / max((y != "poor").sum(), 1))}
    if "blurred" in df and "blur" in df:
        thr = a.blur_threshold if a.blur_threshold is not None else float(df.blur[df.blurred == 0].quantile(.05)) if (df.blurred == 0).any() else 13.0
        pred_blur = df.blur < thr
        out["blur_detection"] = {"threshold": thr, "accuracy": float((pred_blur == (df.blurred == 1)).mean())}
        order = df.blur.values
        from sklearn.metrics import roc_auc_score
        if df.blurred.nunique() == 2:
            out["blur_detection"]["auc"] = float(roc_auc_score(df.blurred, -order))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

