"""Train one model on one fold (or one fixed split) with transfer learning, imbalance handling and calibration.

    python train.py --arch efficientnet_b0 --folds data/splits/folds.csv --fold 0 --cache data/pad_ufes_20/roi256 \
                    --imbalance weighted_loss --epochs 30 --out runs/m2/efficientnet_b0/fold0

--imbalance: none | weighted_loss | focal | sampler    (choose one; combining them double-counts the correction)
Phase 1 trains only the new head (--freeze-epochs), phase 2 fine-tunes everything with a lower backbone learning rate.
After training the best checkpoint (by validation --monitor) gets a temperature fitted on the validation set so the
reported confidence is calibrated; test predictions are written with that temperature applied.
--final trains the deployment model on every fold except one (used only for early stopping); no test metrics exist for it.
"""
import argparse
import hashlib
import json
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

import metrics as M
from classes import PAD_UFES_20_CLASSES, class_order
from data_module import DATASET, RoiDataset, resolve_splits
from losses import make_loss
from models import ARCHS, build_model, freeze_backbone_bn, set_backbone_trainable, split_params

DEFAULT_LR = {"simple_cnn": 1e-3}


def sha256_of(*paths) -> str | None:
    """Fingerprint of the split file(s), stored in meta.json so a deployed model can be traced to the exact data split."""
    h, found = hashlib.sha256(), False
    for p in paths:
        if p and Path(p).is_file():
            h.update(Path(p).read_bytes()); found = True
    return h.hexdigest()[:16] if found else None


def seed_all(s: int) -> None:
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)


@torch.no_grad()
def logits_of(model, loader, device):
    model.eval()
    out, ys = [], []
    for x, y in loader:
        out.append(model(x.to(device, non_blocking=True)).float().cpu()); ys.append(y)
    return torch.cat(out), torch.cat(ys)


def fit_temperature(logits: torch.Tensor, y: torch.Tensor) -> float:
    """Single scalar T minimising validation NLL (temperature scaling, Guo et al. 2017)."""
    logt = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([logt], lr=0.1, max_iter=100)
    def closure():
        opt.zero_grad(); loss = nn.functional.cross_entropy(logits / logt.exp(), y); loss.backward(); return loss
    opt.step(closure)
    return float(logt.exp().clamp(0.05, 20.0).detach())


def write_probs(df, probs, classes, path):
    out = df[["image_id", "group_id", "label_idx"]].reset_index(drop=True).copy()
    for i, c in enumerate(classes):
        out[f"p_{c}"] = probs[:, i]
    out.to_csv(path, index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arch", choices=ARCHS, required=True)
    ap.add_argument("--folds", default=None, help="folds.csv from prepare_dataset.py --kfold")
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--splits", default=None, help="folder with train/val/test.csv instead of --folds")
    ap.add_argument("--final", action="store_true", help="train the deployment model on all but one fold (no test set)")
    ap.add_argument("--cache", required=True, help="ROI crop folder from precompute_rois.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--freeze-epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=None, help="head lr (default 3e-4; 1e-3 for simple_cnn)")
    ap.add_argument("--backbone-lr-mult", type=float, default=0.1)
    ap.add_argument("--weight-decay", type=float, default=1e-2)
    ap.add_argument("--imbalance", choices=["none", "weighted_loss", "focal", "sampler"], default="weighted_loss")
    ap.add_argument("--weight-power", type=float, default=1.0, help="1 = inverse frequency, 0.5 = square root")
    ap.add_argument("--gamma", type=float, default=2.0)
    ap.add_argument("--label-smoothing", type=float, default=0.0)
    ap.add_argument("--aug", choices=["basic", "strong"], default="basic")
    ap.add_argument("--monitor", choices=["macro_f1", "balanced_accuracy", "loss"], default="macro_f1")
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--no-pretrained", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true", help="continue from <out>/last.pt (model, optimiser, epoch, best score, history)")
    ap.add_argument("--keep-top-k", type=int, default=3, help="keep this many best checkpoints in <out>/checkpoints/ (best.pt is always kept)")
    ap.add_argument("--max-batches", type=int, default=0, help="debug: limit batches per epoch")
    ap.add_argument("--mlflow", action="store_true", help="log params, per-epoch metrics and artifacts to MLflow (pip install mlflow; MLFLOW_TRACKING_URI optional)")
    a = ap.parse_args()
    if not a.folds and not a.splits:
        raise SystemExit("Give --folds folds.csv or --splits <dir>.")
    seed_all(a.seed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    classes = class_order(DATASET); K = len(classes)

    mlf = None
    if a.mlflow:
        try:
            import mlflow as mlf
            mlf.set_experiment("dermai")
            mlf.start_run(run_name=f"{a.arch}-{out.parent.name}-{out.name}")
            mlf.log_params({k: str(v) for k, v in vars(a).items()})
        except ImportError:
            print("MLflow not installed (pip install mlflow); continuing without it."); mlf = None
    train_df, val_df, test_df = resolve_splits(a.folds, a.splits, a.fold, a.final)
    assert not set(train_df.group_id) & set(val_df.group_id), "patient leakage train/val"
    if test_df is not None:
        assert not set(train_df.group_id) & set(test_df.group_id) and not set(val_df.group_id) & set(test_df.group_id), "patient leakage into test"
    counts = np.bincount(train_df.label_idx, minlength=K)
    print(f"{a.arch} on {dev} | train {len(train_df)} val {len(val_df)} test {0 if test_df is None else len(test_df)} | train class counts {dict(zip(classes, counts.tolist()))}")

    tr = RoiDataset(train_df, a.cache, True, a.size, a.aug)
    va = RoiDataset(val_df, a.cache, False, a.size)
    te = RoiDataset(test_df, a.cache, False, a.size) if test_df is not None else None
    kw = dict(num_workers=a.workers, pin_memory=dev.type == "cuda", persistent_workers=a.workers > 0)
    sampler = None
    if a.imbalance == "sampler":
        w = (1.0 / np.maximum(counts, 1)) ** a.weight_power
        sampler = WeightedRandomSampler(torch.tensor(w[train_df.label_idx.values], dtype=torch.double), len(train_df), replacement=True)
    tl = DataLoader(tr, a.batch, shuffle=sampler is None, sampler=sampler, drop_last=len(tr) > a.batch, **kw)
    vl = DataLoader(va, a.batch * 2, **kw)

    model = build_model(a.arch, K, pretrained=not a.no_pretrained).to(dev)
    pretrained = not a.no_pretrained and a.arch != "simple_cnn"
    freeze = a.freeze_epochs if pretrained else 0
    lr = a.lr or DEFAULT_LR.get(a.arch, 3e-4)
    back, head = split_params(model, a.arch)
    mult = a.backbone_lr_mult if pretrained else 1.0
    opt = torch.optim.AdamW([{"params": back, "lr": lr * mult, "base": lr * mult}, {"params": head, "lr": lr, "base": lr}], weight_decay=a.weight_decay)
    loss_fn = make_loss(a.imbalance, counts, a.weight_power, a.gamma, a.label_smoothing).to(dev)
    use_amp = dev.type == "cuda"
    scaler = torch.amp.GradScaler(enabled=use_amp)

    def lr_factor(ep):                 # 1 warm-up epoch, then cosine to 2%
        if ep == 0:
            return 0.3
        return 0.02 + 0.98 * 0.5 * (1 + math.cos(math.pi * (ep - 1) / max(a.epochs - 1, 1)))

    best, best_ep, bad, history = None, -1, 0, []
    score_of = lambda m: -m["loss"] if a.monitor == "loss" else m[a.monitor]
    start_ep = 0
    ck_dir = out / "checkpoints"; ck_dir.mkdir(exist_ok=True)
    if a.resume and (out / "last.pt").exists():
        st = torch.load(out / "last.pt", map_location=dev)
        model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"])
        start_ep, best, best_ep, bad, history = st["epoch"] + 1, st["best"], st["best_ep"], st["bad"], st["history"]
        print(f"resumed from epoch {st['epoch']} (best {best:.4f} at epoch {best_ep})")
    if freeze and start_ep < freeze:
        set_backbone_trainable(model, a.arch, False)
    for ep in range(start_ep, a.epochs):
        if freeze and ep == freeze:
            set_backbone_trainable(model, a.arch, True)
            print(f"epoch {ep}: backbone unfrozen")
        for g in opt.param_groups:
            g["lr"] = g["base"] * lr_factor(ep)
        model.train()
        if freeze and ep < freeze:
            freeze_backbone_bn(model, a.arch)
        t0, run, nb = time.time(), 0.0, 0
        for bi, (x, y) in enumerate(tl):
            if a.max_batches and bi >= a.max_batches:
                break
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(dev.type, enabled=use_amp):
                loss = loss_fn(model(x), y)
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            run += loss.item(); nb += 1
        lg, yv = logits_of(model, vl, dev)
        m = M.compute(yv.numpy(), torch.softmax(lg, 1).numpy(), classes)
        m["loss"] = float(nn.functional.cross_entropy(lg, yv))
        history.append({"epoch": ep, "train_loss": run / max(nb, 1), "val_loss": m["loss"], "val_macro_f1": m["macro_f1"],
                        "val_balanced_acc": m["balanced_accuracy"], "val_acc": m["accuracy"], "secs": round(time.time() - t0, 1)})
        if mlf:
            mlf.log_metrics({"train_loss": run / max(nb, 1), "val_loss": m["loss"], "val_macro_f1": m["macro_f1"], "val_balanced_acc": m["balanced_accuracy"]}, step=ep)
        print(f"epoch {ep:02d} train {run / max(nb, 1):.3f} | val loss {m['loss']:.3f} macroF1 {m['macro_f1']:.3f} balAcc {m['balanced_accuracy']:.3f} | {time.time() - t0:.0f}s")
        if best is None or score_of(m) > best:
            best, best_ep, bad = score_of(m), ep, 0
            torch.save(model.state_dict(), out / "best.pt")
            if a.keep_top_k > 1:
                torch.save(model.state_dict(), ck_dir / f"ep{ep:03d}_{best:.4f}.pt")
                for old in sorted(ck_dir.glob("ep*.pt"), key=lambda f: float(f.stem.split("_")[1]))[:-a.keep_top_k]:
                    old.unlink()
        else:
            bad += 1
            if ep >= freeze + 3 and bad >= a.patience:
                print(f"early stop at epoch {ep} (best {best_ep})")
                torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "epoch": ep, "best": best, "best_ep": best_ep, "bad": bad, "history": history}, out / "last.pt")
                break
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "epoch": ep, "best": best, "best_ep": best_ep, "bad": bad, "history": history}, out / "last.pt")
    pd.DataFrame(history).to_csv(out / "history.csv", index=False)

    model.load_state_dict(torch.load(out / "best.pt", map_location=dev))
    lg, yv = logits_of(model, vl, dev)
    T = fit_temperature(lg, yv)
    res = {"arch": a.arch, "best_epoch": best_ep, "temperature": T, "fold": None if a.final or not a.folds else a.fold, "final_model": a.final}
    res["val"] = M.compute(yv.numpy(), torch.softmax(lg / T, 1).numpy(), classes)
    write_probs(val_df, torch.softmax(lg / T, 1).numpy(), classes, out / "val_probs.csv")
    if te is not None:
        lt, yt = logits_of(model, DataLoader(te, a.batch * 2, **kw), dev)
        pt = torch.softmax(lt / T, 1).numpy()
        res["test"] = M.compute(yt.numpy(), pt, classes)
        res["test_uncalibrated_ece"] = M.ece(torch.softmax(lt, 1).numpy(), yt.numpy())
        write_probs(test_df, pt, classes, out / "test_probs.csv")
        print(f"TEST macroF1 {res['test']['macro_f1']:.3f} balAcc {res['test']['balanced_accuracy']:.3f} acc {res['test']['accuracy']:.3f} "
              f"AUC {res['test']['macro_auc_ovr']:.3f} ECE {res['test']['ece']:.3f} (T={T:.2f})")
    (out / "metrics.json").write_text(json.dumps(res, indent=2))
    preproc = Path(a.cache) / "preproc.txt"
    (out / "meta.json").write_text(json.dumps({
        "arch": a.arch, "classes": classes, "class_names": PAD_UFES_20_CLASSES, "img_size": a.size,
        "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225], "temperature": T, "dataset": "PAD-UFES-20",
        "preprocessing": preproc.read_text().strip() if preproc.exists() else "unknown", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "args": vars(a), "final_model": a.final, "best_epoch": best_ep, "n_train": len(train_df), "n_val": len(val_df),
        "folds_sha256": sha256_of(a.folds) if a.folds else sha256_of(*(Path(a.splits) / f"{n}.csv" for n in ("train", "val", "test"))),
    }, indent=2, default=str))
    if mlf:
        flat = {f"final_{k}": v for k, v in (res.get("test") or res["val"]).items() if isinstance(v, float)}
        mlf.log_metrics(flat); mlf.log_param("temperature", T)
        for f in ("metrics.json", "meta.json", "history.csv", "best.pt"):
            if (out / f).exists():
                mlf.log_artifact(str(out / f))
        mlf.end_run()
    print(f"saved to {out}/")


if __name__ == "__main__":
    main()

