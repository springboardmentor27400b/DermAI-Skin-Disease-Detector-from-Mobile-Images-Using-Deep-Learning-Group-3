"""Train a lesion segmentation model once you have masks (PAD-UFES-20 ships none).

    # honest accuracy estimate (5-fold cross-validation, resumable) AND a deployable model:
    python train_seg.py --images data/to_annotate --masks data/masks --out runs/seg/unet_cv --cv 5 --export-dir ../backend/models
    # quick single split instead:
    python train_seg.py --images data/to_annotate --masks data/masks --out runs/seg/unet

Masks: one binary PNG per photo named <image stem>.png (white = lesion); make them with annotate_masks.py.
Splits are grouped by patient (PAT_<id> in the file name). With --cv every photo is scored once by a model that never saw it
(cv_scores.csv), which is far more reliable than a ~20-photo test split. --export-dir then trains the deployment model on all
folds but one (used for early stopping) and writes segmentation.ts.pt + segmentation.json, which the API picks up automatically.
Resumable: finished folds are skipped when you run the same command again.
"""
import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from seg_metrics import mean_scores, seg_scores
from seg_models import SEG_ARCHS, build_seg_model, dice_bce_loss

MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
EXTS = (".png", ".jpg", ".jpeg")


def load_item(ip: Path, mp: Path, size: int):
    img = cv2.cvtColor(cv2.imread(str(ip)), cv2.COLOR_BGR2RGB)
    m = (cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA), cv2.resize(m, (size, size), interpolation=cv2.INTER_NEAREST)


def augment(img: np.ndarray, m: np.ndarray):
    """Random rotation, scale, shift and flip applied identically to photo and mask, plus mild brightness/contrast/saturation."""
    s = img.shape[0]
    M = cv2.getRotationMatrix2D((s / 2, s / 2), random.uniform(0, 360), random.uniform(0.8, 1.25))
    M[:, 2] += [random.uniform(-0.08, 0.08) * s, random.uniform(-0.08, 0.08) * s]
    img = cv2.warpAffine(img, M, (s, s), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    m = cv2.warpAffine(m, M, (s, s), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    if random.random() < .5:
        img, m = img[:, ::-1], m[:, ::-1]
    x = img.astype(np.float32)
    x = (x - 128) * random.uniform(.85, 1.15) + 128 + random.uniform(-20, 20)
    g = x.mean(2, keepdims=True); x = g + (x - g) * random.uniform(.85, 1.15)
    return np.clip(x, 0, 255), m


class SegData(Dataset):
    def __init__(self, items, size, train):
        self.items, self.size, self.train = items, size, train

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        img, m = load_item(*self.items[i], self.size)
        if self.train:
            img, m = augment(img, m)
        x = ((np.asarray(img, np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)
        return torch.from_numpy(np.ascontiguousarray(x)), torch.from_numpy(np.ascontiguousarray(m[None].astype(np.float32)))


@torch.no_grad()
def predict_scores(model, items, dev, size, batch=16):
    """Per-image scores at the working resolution."""
    model.eval()
    rows, k = [], 0
    for x, y in DataLoader(SegData(items, size, False), batch):
        p = (torch.sigmoid(model(x.to(dev))) > .5).cpu().numpy()[:, 0]
        for pi, yi in zip(p, y.numpy()[:, 0]):
            rows.append({"image": items[k][0].name, **seg_scores(pi, yi)}); k += 1
    return rows


def fit(arch, tr, va, a, dev, out: Path, seed: int):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    out.mkdir(parents=True, exist_ok=True)
    tl = DataLoader(SegData(tr, a.size, True), a.batch, shuffle=True, num_workers=a.workers, drop_last=len(tr) > a.batch)
    model = build_seg_model(arch, not a.no_pretrained).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs)
    use_amp = dev.type == "cuda"
    scaler = torch.amp.GradScaler(enabled=use_amp)
    best, bad = -1.0, 0
    for ep in range(a.epochs):
        model.train(); tot = 0.0
        for x, y in tl:
            x, y = x.to(dev), y.to(dev)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(dev.type, enabled=use_amp):
                out_logits = model(x)
            loss = dice_bce_loss(out_logits.float(), y)
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); tot += loss.item()
        sched.step()
        v = mean_scores(predict_scores(model, va, dev, a.size))
        if (ep + 1) % 5 == 0 or ep == 0:
            print(f"  epoch {ep:02d} loss {tot / max(len(tl), 1):.3f} | val Dice {v['dice']:.3f} IoU {v['iou']:.3f}")
        if v["dice"] > best:
            best, bad = v["dice"], 0; torch.save(model.state_dict(), out / "best.pt")
        else:
            bad += 1
            if bad >= a.patience:
                print(f"  early stop at epoch {ep}"); break
    model.load_state_dict(torch.load(out / "best.pt", map_location=dev))
    return model, best


def export(model, a, evaluation):
    model.eval().cpu()
    ts = torch.jit.trace(model, torch.randn(1, 3, a.size, a.size), check_trace=False)
    d = Path(a.export_dir); d.mkdir(parents=True, exist_ok=True)
    ts.save(str(d / "segmentation.ts.pt"))
    (d / "segmentation.json").write_text(json.dumps({"arch": a.arch, "img_size": a.size, "mean": MEAN.tolist(), "std": STD.tolist(), "evaluation": evaluation}, indent=2))
    print(f"exported segmentation model to {d}/  (restart the API or POST /api/models/reload)")


def boot_ci(v, n=1000, seed=0):
    r = np.random.default_rng(seed); v = np.asarray(v)
    m = [r.choice(v, len(v)).mean() for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arch", choices=SEG_ARCHS, default="unet_resnet34")
    ap.add_argument("--images", required=True); ap.add_argument("--masks", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--cv", type=int, default=0, help="k-fold cross-validation over the annotated photos (0 = one split)")
    ap.add_argument("--export-dir", default=None)
    ap.add_argument("--size", type=int, default=256); ap.add_argument("--epochs", type=int, default=60); ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4); ap.add_argument("--patience", type=int, default=12)
    ap.add_argument("--no-pretrained", action="store_true"); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    imgs = {p.stem: p for p in Path(a.images).iterdir() if p.suffix.lower() in EXTS}
    pairs = [(imgs[m.stem], m) for m in sorted(Path(a.masks).glob("*.png")) if m.stem in imgs]
    if len(pairs) < 20:
        raise SystemExit(f"Only {len(pairs)} image/mask pairs found; annotate at least ~50 (ideally 150+).")
    group = lambda p: "_".join(p[0].stem.split("_")[:2]) if p[0].stem.startswith("PAT_") else p[0].stem
    groups = sorted({group(p) for p in pairs}); random.Random(a.seed).shuffle(groups)
    K = a.cv
    print(f"{a.arch} on {dev}: {len(pairs)} annotated photos, {len(groups)} patients" + (f", {K}-fold CV" if K else ""))

    if K:
        fold_of = {g: i % K for i, g in enumerate(groups)}
        allrows = []
        for f in range(K):
            fd = out / f"fold{f}"
            sf = fd / "scores.csv"
            if sf.exists():
                print(f"fold {f}: done (skipped)"); allrows.append(pd.read_csv(sf)); continue
            val_f = (f + 1) % K
            te = [p for p in pairs if fold_of[group(p)] == f]
            va = [p for p in pairs if fold_of[group(p)] == val_f]
            tr = [p for p in pairs if fold_of[group(p)] not in (f, val_f)]
            print(f"fold {f}: train {len(tr)} val {len(va)} test {len(te)}")
            model, _ = fit(a.arch, tr, va, a, dev, fd, a.seed + f)
            df = pd.DataFrame(predict_scores(model, te, dev, a.size)); df["fold"] = f
            df.to_csv(sf, index=False); allrows.append(df)
            print(f"fold {f}: test Dice {df.dice.mean():.3f} IoU {df.iou.mean():.3f}")
        cv = pd.concat(allrows, ignore_index=True)
        cv.to_csv(out / "cv_scores.csv", index=False)
        fin = cv.replace([np.inf], np.nan)
        lo, hi = boot_ci(cv.dice)
        summary = {"arch": a.arch, "images": len(cv), "dice": float(cv.dice.mean()), "dice_ci95": [lo, hi], "iou": float(cv.iou.mean()),
                   "pixel_accuracy": float(cv.pixel_accuracy.mean()), "sensitivity": float(cv.sensitivity.mean()), "specificity": float(cv.specificity.mean()),
                   "hausdorff_px_mean": float(fin.hausdorff_px.mean()), "dice_by_fold": {int(k): round(float(v), 3) for k, v in cv.groupby("fold").dice.mean().items()},
                   "failures_dice_below_0.5": int((cv.dice < 0.5).sum()), "scored_at_px": a.size}
        (out / "cv_summary.json").write_text(json.dumps(summary, indent=2))
        print("\nCROSS-VALIDATED:", json.dumps(summary, indent=2))
        if a.export_dir:
            print("training the deployment model (all folds except one used for early stopping)")
            va = [p for p in pairs if fold_of[group(p)] == 0]
            tr = [p for p in pairs if fold_of[group(p)] != 0]
            model, _ = fit(a.arch, tr, va, a, dev, out / "final", a.seed + 99)
            export(model, a, {**summary, "source": f"{K}-fold cross-validation on {len(pairs)} annotated photos"})
        return

    val_g, test_g = set(groups[:int(.15 * len(groups))]), set(groups[int(.15 * len(groups)):int(.30 * len(groups))])
    va = [p for p in pairs if group(p) in val_g]; te = [p for p in pairs if group(p) in test_g]
    tr = [p for p in pairs if group(p) not in val_g | test_g]
    print(f"train {len(tr)} val {len(va)} test {len(te)} (patient-grouped)")
    model, _ = fit(a.arch, tr, va, a, dev, out, a.seed)
    res = {"arch": a.arch, "val": mean_scores(predict_scores(model, va, dev, a.size)), "test": mean_scores(predict_scores(model, te, dev, a.size)) if te else None, "n_pairs": len(pairs)}
    (out / "metrics.json").write_text(json.dumps(res, indent=2))
    print("TEST", json.dumps(res["test"]))
    if a.export_dir:
        export(model, a, res["test"] or res["val"])


if __name__ == "__main__":
    main()

