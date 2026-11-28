"""Classification metrics used for model comparison (brief sections 10, 12 and 9)."""
import numpy as np
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix, matthews_corrcoef,
                             precision_recall_fscore_support, roc_auc_score)

# Dataset-defined: every BCC, SCC and MEL in PAD-UFES-20 is biopsy-confirmed skin cancer. Used only to report a
# cancer-vs-other sensitivity; it is not a clinical risk threshold.
MALIGNANT = ("BCC", "SCC", "MEL")


def ece(probs: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    conf, pred = probs.max(1), probs.argmax(1)
    edges, total = np.linspace(0, 1, bins + 1), 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(total)


def compute(y: np.ndarray, probs: np.ndarray, classes: list[str]) -> dict:
    k = len(classes)
    pred = probs.argmax(1)
    cm = confusion_matrix(y, pred, labels=range(k))
    p, r, f, sup = precision_recall_fscore_support(y, pred, labels=range(k), zero_division=0)
    tn = cm.sum() - cm.sum(0) - cm.sum(1) + np.diag(cm)
    fp = cm.sum(0) - np.diag(cm)
    spec = np.divide(tn, tn + fp, out=np.zeros(k), where=(tn + fp) > 0)
    auc = []
    for i in range(k):
        auc.append(float(roc_auc_score((y == i).astype(int), probs[:, i])) if 0 < (y == i).sum() < len(y) else float("nan"))
    present = sup > 0
    out = {
        "n": int(len(y)),
        "accuracy": float((pred == y).mean()),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_precision": float(p[present].mean()), "macro_recall": float(r[present].mean()), "macro_f1": float(f[present].mean()),
        "weighted_f1": float(np.average(f, weights=sup)) if sup.sum() else 0.0,
        "mcc": float(matthews_corrcoef(y, pred)),
        "macro_auc_ovr": float(np.nanmean(auc)),
        "top2_accuracy": float((np.argsort(-probs, 1)[:, :2] == y[:, None]).any(1).mean()),
        "ece": ece(probs, y),
        "per_class": {c: {"precision": float(p[i]), "recall_sensitivity": float(r[i]), "specificity": float(spec[i]),
                          "f1": float(f[i]), "auc_ovr": auc[i], "support": int(sup[i])} for i, c in enumerate(classes)},
        "confusion_matrix": cm.tolist(),
        "classes": classes,
    }
    mal = [classes.index(c) for c in MALIGNANT if c in classes]
    if mal:
        yt, yp = np.isin(y, mal), np.isin(pred, mal)
        out["malignant_vs_other"] = {"classes": [classes[i] for i in mal],
                                     "sensitivity": float((yt & yp).sum() / max(yt.sum(), 1)),
                                     "specificity": float((~yt & ~yp).sum() / max((~yt).sum(), 1))}
    return out

