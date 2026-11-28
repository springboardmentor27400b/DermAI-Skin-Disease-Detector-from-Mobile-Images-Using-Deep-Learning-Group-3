"""Pick a diverse set of photos to annotate with lesion masks (stratified by diagnosis, one photo per patient).

    python sample_for_annotation.py --metadata data/pad_ufes_20/metadata.csv --images data/pad_ufes_20/images --n 150 --out data/to_annotate \
        --lesions-csv data/pad_ufes_20/roi256/lesions.csv --hard-frac 0.5
--hard-frac takes that share of photos from those where the old detector found NO lesion: the cases a trained model must learn.
Copies the chosen photos so you can annotate them with annotate_masks.py.
"""
import argparse
import shutil
from pathlib import Path

import pandas as pd

from datasets import SPECS, load


def stratified(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if n <= 0 or df.empty:
        return df.iloc[0:0]
    per = max(1, n // df.label.nunique())
    pick = pd.concat([g.sample(min(len(g), per), random_state=seed) for _, g in df.groupby("label")])
    if len(pick) < n:                                         # top up from what is left
        rest = df.drop(pick.index)
        pick = pd.concat([pick, rest.sample(min(len(rest), n - len(pick)), random_state=seed)])
    return pick.head(n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True); ap.add_argument("--images", required=True); ap.add_argument("--out", default="data/to_annotate")
    ap.add_argument("--n", type=int, default=150); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lesions-csv", default=None, help="lesions.csv written by precompute_rois.py (has a 'found' column)")
    ap.add_argument("--hard-frac", type=float, default=0.5, help="share taken from photos where the detector found nothing (needs --lesions-csv)")
    a = ap.parse_args()
    df = load(SPECS["pad_ufes_20"], a.metadata).dropna(subset=["label"]).sample(frac=1, random_state=a.seed)
    if a.lesions_csv:
        les = pd.read_csv(a.lesions_csv)
        found = dict(zip(les.image_id.map(lambda s: Path(str(s)).name), les.found))
        df["found"] = df.image_id.map(lambda s: bool(found.get(Path(str(s)).name, True)))
        hard = stratified(df[~df.found].drop_duplicates("group_id"), round(a.n * a.hard_frac), a.seed)
        easy_pool = df[~df.group_id.isin(hard.group_id)].drop_duplicates("group_id")
        pick = pd.concat([hard, stratified(easy_pool, a.n - len(hard), a.seed)])
        print(f"{len(hard)} 'detector found nothing' photos + {len(pick) - len(hard)} others")
    else:
        pick = stratified(df.drop_duplicates("group_id"), a.n, a.seed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    copied = 0
    for iid in pick.image_id:
        src = next((p for p in (Path(a.images) / iid, *[Path(a.images) / f"{iid}{e}" for e in (".png", ".jpg", ".jpeg")]) if p.exists()), None)
        if src:
            shutil.copy(src, out / src.name); copied += 1
    print(f"copied {copied} photos to {out} (class-balanced, one per patient)")


if __name__ == "__main__":
    main()

