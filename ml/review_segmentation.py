"""Why do some photos score badly, and what cheap post-processing helps? Uses the fold models saved by train_seg.py --cv (no retraining).

    python review_segmentation.py --images data/to_annotate --masks data/masks --runs runs/seg/unet_cv --cv 5
Re-scores every photo with the model that never saw it, in four ways: raw, + cleanup (keep the one region nearest the centre, fill
holes: what the API does), + flip averaging (test-time augmentation), and both. Then draws the worst photos: GREEN = your mask,
RED = the model. Read the sheet to tell annotation inconsistency (green and red both look reasonable) from real model errors.
Use the same --seed/--size/--arch as training.
"""
import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch

from seg_metrics import seg_scores
from seg_models import SEG_ARCHS, build_seg_model
from train_seg import EXTS, MEAN, STD, load_item

S = 256


def clean(mask: np.ndarray) -> np.ndarray:
    """Keep the single region nearest the centre (area-weighted), fill its holes."""
    h, w = mask.shape
    n, lbl, st, cent = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 1:
        return mask.astype(np.uint8)
    diag = np.hypot(h, w)
    score = [st[i, cv2.CC_STAT_AREA] * np.exp(-(np.hypot(cent[i][0] - w / 2, cent[i][1] - h / 2) / (0.35 * diag)) ** 2) for i in range(1, n)]
    m = (lbl == 1 + int(np.argmax(score))).astype(np.uint8)
    flood = m.copy(); cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    return m | (1 - flood)


@torch.no_grad()
def probs(model, x, dev, tta: bool):
    p = torch.sigmoid(model(x.to(dev)))
    if tta:
        p = p + torch.sigmoid(model(x.flip(3).to(dev))).flip(3) + torch.sigmoid(model(x.flip(2).to(dev))).flip(2) + torch.sigmoid(model(x.flip(2).flip(3).to(dev))).flip(2).flip(3)
        p = p / 4
    return p[0, 0].cpu().numpy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True); ap.add_argument("--masks", required=True); ap.add_argument("--runs", required=True)
    ap.add_argument("--cv", type=int, default=5); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--arch", choices=SEG_ARCHS, default="unet_resnet34"); ap.add_argument("--worst", type=int, default=24)
    ap.add_argument("--out", default="reports/segmentation")
    ap.add_argument("--list-below", type=float, default=0.5, help="write photos with Dice below this to worst_cases.txt (for annotate_masks.py --redo)")
    a = ap.parse_args()
    global S
    S = a.size
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    imgs = {p.stem: p for p in Path(a.images).iterdir() if p.suffix.lower() in EXTS}
    pairs = [(imgs[m.stem], m) for m in sorted(Path(a.masks).glob("*.png")) if m.stem in imgs]
    group = lambda p: "_".join(p[0].stem.split("_")[:2]) if p[0].stem.startswith("PAT_") else p[0].stem
    groups = sorted({group(p) for p in pairs}); random.Random(a.seed).shuffle(groups)
    fold_of = {g: i % a.cv for i, g in enumerate(groups)}
    rows, keep = [], {}
    for f in range(a.cv):
        ck = Path(a.runs) / f"fold{f}" / "best.pt"
        if not ck.exists():
            raise SystemExit(f"missing {ck}; run train_seg.py --cv {a.cv} first")
        model = build_seg_model(a.arch, pretrained=False).to(dev).eval()
        model.load_state_dict(torch.load(ck, map_location=dev))
        for ip, mp in [p for p in pairs if fold_of[group(p)] == f]:
            img, gt = load_item(ip, mp, a.size)
            x = torch.from_numpy(np.ascontiguousarray(((img.astype(np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)))[None]
            p1, p4 = probs(model, x, dev, False), probs(model, x, dev, True)
            v = {"raw": (p1 > .5).astype(np.uint8), "cleanup": clean(p1 > .5), "flip_avg": (p4 > .5).astype(np.uint8), "cleanup+flip_avg": clean(p4 > .5)}
            for name, m in v.items():
                rows.append({"image": ip.name, "variant": name, **seg_scores(m, gt)})
            keep[ip.name] = (img, gt, v["cleanup+flip_avg"])
    df = pd.DataFrame(rows)
    summ = []
    for name, g in df.groupby("variant", sort=False):
        fin = g.replace([np.inf], np.nan)
        summ.append({"variant": name, "dice": round(g.dice.mean(), 3), "iou": round(g.iou.mean(), 3), "hausdorff_px": round(fin.hausdorff_px.mean(), 1),
                     "dice_below_0.5": int((g.dice < .5).sum()), "empty_predictions": int((g.sensitivity == 0).sum())})
    sm = pd.DataFrame(summ)
    print(sm.to_string(index=False))
    area = {k: float(v[1].mean()) for k, v in keep.items()}           # lesion size = share of the photo covered by YOUR mask
    df["lesion_area_frac"] = df.image.map(area)
    b = df[df.variant == "cleanup+flip_avg"].copy()
    b["size_group"] = pd.qcut(b.lesion_area_frac, 4, labels=["smallest 25%", "small-mid", "large-mid", "largest 25%"], duplicates="drop")
    bs = b.groupby("size_group", observed=True).agg(photos=("dice", "size"), lesion_area=("lesion_area_frac", "mean"), dice=("dice", "mean"), below_0_5=("dice", lambda s: int((s < .5).sum()))).round(3)
    print("\nDice by lesion size (share of photo covered):\n" + bs.to_string())
    print(f"Dice quartiles over all photos: 25% {b.dice.quantile(.25):.2f}, median {b.dice.median():.2f}, 75% {b.dice.quantile(.75):.2f}")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    bs.to_csv(out / "dice_by_lesion_size.csv")
    df.to_csv(out / "cv_variants_scores.csv", index=False); sm.to_csv(out / "cv_variants_summary.csv", index=False)

    ranked = df[df.variant == "cleanup+flip_avg"].sort_values("dice")
    low = ranked[ranked.dice < a.list_below]
    (out / "worst_cases.txt").write_text("\n".join(low.image) + "\n")
    print(f"{len(low)} photos below Dice {a.list_below} listed in {out / 'worst_cases.txt'} (re-check with annotate_masks.py --redo)")
    best = ranked.head(a.worst)
    T, cols = 200, 6
    rows_n = (len(best) + cols - 1) // cols
    sheet = np.full((rows_n * (T + 18), cols * T, 3), 255, np.uint8)
    for i, (_, r) in enumerate(best.iterrows()):
        img, gt, pr = keep[r.image]
        vis = cv2.resize(img, (T - 4, T - 4), interpolation=cv2.INTER_AREA)
        for m, col in ((gt, (30, 200, 60)), (pr, (230, 40, 40))):
            c, _ = cv2.findContours(cv2.resize(m.astype(np.uint8), (T - 4, T - 4), interpolation=cv2.INTER_NEAREST), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, c, -1, col, 2)
        y, x = (i // cols) * (T + 18), (i % cols) * T
        sheet[y + 2:y + T - 2, x + 2:x + T - 2] = vis
        cv2.putText(sheet, f"Dice {r.dice:.2f}", (x + 4, y + T + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(str(out / "worst_cases.png"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print(f"\nWorst {len(best)} photos (green = your mask, red = model): {out / 'worst_cases.png'}")


if __name__ == "__main__":
    main()

