"""One-page evaluation summary of everything measured so far: classification error, where the errors are, segmentation and image quality.

    python evaluation_summary.py --comparison reports/m2_sampler/comparison.json --model convnext_tiny \
        --seg ../backend/models/segmentation.json --quality reports/quality/summary.json --out reports/final_evaluation.md
Reads only files you already have (compare_models.py / train_seg.py / quality_audit.py outputs). Writes markdown you can paste into the report.
"""
import argparse
import json
from pathlib import Path

import numpy as np

MALIGNANT = ("BCC", "SCC", "MEL")


def load(path):
    p = Path(path) if path else None
    return json.loads(p.read_text()) if p and p.is_file() else None


def classification(c: dict) -> list[str]:
    cm, cls = np.array(c["confusion_matrix"]), c["classes"]
    n, right = int(cm.sum()), int(np.trace(cm))
    L = [f"## Classification (pooled out-of-fold, patient-grouped 5-fold CV, {n} images)", "",
         f"- **Error rate: {(n - right) / n * 100:.1f}%** ({n - right} of {n} images wrong); accuracy {right / n * 100:.1f}%",
         f"- Balanced accuracy {c['balanced_accuracy']:.3f}, macro-F1 {c['macro_f1']:.3f}, macro AUC {c['macro_auc_ovr']:.3f}, MCC {c['mcc']:.3f}",
         f"- Top-2 accuracy {c['top2_accuracy'] * 100:.1f}% (the true class is among the two most likely in that share of images)",
         f"- Calibration error (ECE) {c['ece']:.3f}", ""]
    mal = [cls.index(m) for m in MALIGNANT if m in cls]
    ben = [i for i in range(len(cls)) if i not in mal]
    if mal:
        tp = int(cm[np.ix_(mal, mal)].sum()); pos = int(cm[mal].sum()); neg = int(cm[ben].sum())
        fp = int(cm[np.ix_(ben, mal)].sum())
        missed = int(cm[np.ix_(mal, ben)].sum())
        L += ["### Skin cancer (BCC, SCC, melanoma) versus the rest",
              f"- Sensitivity {tp / pos * 100:.1f}%: {missed} of {pos} cancers were predicted as a benign class (a missed-cancer error)",
              f"- Specificity {(1 - fp / neg) * 100:.1f}%: {fp} of {neg} benign lesions were predicted as a cancer class", ""]
    L += ["### Per class", "", "| Class | Images | Recall | Precision | F1 | Wrong |", "|---|---|---|---|---|---|"]
    for i, k in enumerate(cls):
        s = int(cm[i].sum()); tpi = int(cm[i, i]); pc = int(cm[:, i].sum())
        rec, prec = tpi / max(s, 1), tpi / max(pc, 1)
        f1 = 2 * rec * prec / max(rec + prec, 1e-9)
        L.append(f"| {k} | {s} | {rec * 100:.0f}% | {prec * 100:.0f}% | {f1:.2f} | {s - tpi} |")
    off = [(cm[i, j], i, j) for i in range(len(cls)) for j in range(len(cls)) if i != j]
    L += ["", "### Most common mistakes (true class -> predicted class)", ""]
    for v, i, j in sorted(off, reverse=True)[:6]:
        L.append(f"- {cls[i]} -> {cls[j]}: {int(v)} images ({v / cm[i].sum() * 100:.0f}% of all {cls[i]})")
    if "MEL" in cls:
        m = cls.index("MEL")
        L += ["", f"### Melanoma: {int(cm[m, m])} of {int(cm[m].sum())} found; missed ones were called " +
              ", ".join(f"{cls[j]} {int(cm[m, j])}" for j in range(len(cls)) if j != m and cm[m, j]) + f". Only about 36 patients, so this number is very uncertain."]
    return L


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comparison", required=True); ap.add_argument("--model", default="convnext_tiny")
    ap.add_argument("--seg", default=None); ap.add_argument("--quality", default=None); ap.add_argument("--out", default="reports/final_evaluation.md")
    a = ap.parse_args()
    comp = load(a.comparison)
    if comp is None or a.model not in comp:
        raise SystemExit(f"{a.model} not found in {a.comparison}")
    out = ["# DermAI evaluation summary", "", f"Model: {a.model}. Screening and research aid, not a diagnosis.", ""] + classification(comp[a.model])
    seg = load(a.seg)
    if seg and seg.get("evaluation"):
        e = seg["evaluation"]
        out += ["", f"## Lesion segmentation ({seg.get('arch')}, {e.get('images')} annotated photos, 5-fold CV)", "",
                f"- Dice {e['dice']:.3f} (95% CI {e['dice_ci95'][0]:.3f}-{e['dice_ci95'][1]:.3f}), IoU {e['iou']:.3f}, pixel accuracy {e['pixel_accuracy']:.3f}",
                f"- Sensitivity {e['sensitivity']:.3f}, specificity {e['specificity']:.3f}, mean Hausdorff {e['hausdorff_px_mean']:.1f} px (at {e.get('scored_at_px')} px)",
                f"- {e['failures_dice_below_0.5']} of {e['images']} photos scored below Dice 0.5"]
    q = load(a.quality)
    if q:
        out += ["", f"## Image quality check ({q['images']} photos)", "",
                "- Rated: " + ", ".join(f"{k} {v}%" for k, v in q["rating_pct"].items()),
                "- Most common flags: " + ", ".join(f"{k} {v}%" for k, v in sorted(q["issue_pct"].items(), key=lambda kv: -kv[1])[:4] if v)]
    out += ["", "## Limits to state", "",
            "- Pooled cross-validation, not a separate untouched test set; the deployed final model has no held-out score of its own.",
            "- 2,298 images, melanoma about 36 patients; ACK, NEV and SEK labels are mostly clinical judgements, not biopsies.",
            "- Fitzpatrick types I to III dominate; performance on darker skin is unknown.",
            "- Results come from one dataset (PAD-UFES-20); behaviour on other phones, lighting and populations is untested."]
    text = "\n".join(out) + "\n"
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

