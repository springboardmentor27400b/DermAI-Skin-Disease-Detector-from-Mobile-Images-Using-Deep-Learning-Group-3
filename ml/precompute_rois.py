"""Detect the lesion in every image and cache the preprocessed ROI crop the classifier trains on.

    python precompute_rois.py --images data/pad_ufes_20/images --out data/pad_ufes_20/roi256 --size 256

Uses exactly the code the API runs (backend/app/preprocessing), so training and inference see the same pixels.
Writes <out>/<image_id>.png and <out>/lesions.csv (found, bbox, area fraction, contrast ratio ... per image).
RESUMABLE: if the run is interrupted (Colab disconnect, Ctrl+C), run the same command again and it continues from the last
finished image. Finished caches are left alone; pass --overwrite to rebuild. A cache is never mixed across recipes.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.preprocessing.lesion import detect_lesion                    # noqa: E402
from app.preprocessing.pipeline import PIPELINE_VERSION, preprocess   # noqa: E402

EXTS = (".png", ".jpg", ".jpeg")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--no-enhance", action="store_true", help="skip denoise / colour-norm / CLAHE / sharpen (ablation)")
    ap.add_argument("--no-hair-removal", action="store_true", help="skip hair removal (ablation)")
    ap.add_argument("--roi-min-frac", type=float, default=0.3, help="smallest ROI side as a fraction of the photo (0.3 default; 0.6-0.8 keeps crops close to the whole photo)")
    ap.add_argument("--no-lesion", action="store_true", help="centre crop instead of lesion ROI (ablation)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true", help="discard any existing or partial cache and rebuild")
    a = ap.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    recipe = f"size={a.size} enhance={not a.no_enhance} lesion_roi={not a.no_lesion} hair_removal={not a.no_hair_removal} roi_min={a.roi_min_frac} pipeline={PIPELINE_VERSION}"
    done_f, prog_f, rec_f = out / "preproc.txt", out / "progress.jsonl", out / "recipe.inprogress"

    if a.overwrite:
        for f in (done_f, prog_f, rec_f):
            f.unlink(missing_ok=True)
    rows: dict[str, dict] = {}
    if done_f.exists():
        if done_f.read_text().strip() != recipe:
            sys.exit(f"{out} already holds a finished cache with a different recipe:\n  {done_f.read_text().strip()}\nChoose another --out, or pass --overwrite.")
        if (out / "lesions.csv").exists():             # finished cache: keep its rows; only images that are new to the folder get processed
            rows = {r["image_id"]: {k: v for k, v in r.items() if not (isinstance(v, float) and np.isnan(v))} for r in pd.read_csv(out / "lesions.csv").to_dict("records")}
            rows = {k: v for k, v in rows.items() if (out / f"{Path(k).stem}.png").exists()}
    else:
        if rec_f.exists() and rec_f.read_text().strip() != recipe:
            sys.exit(f"{out} holds a partial cache built with a different recipe:\n  {rec_f.read_text().strip()}\nChoose another --out, or pass --overwrite.")
        rec_f.write_text(recipe)
        if prog_f.exists():
            for line in prog_f.read_text().splitlines():
                try:
                    r = json.loads(line)
                    if (out / f"{Path(r['image_id']).stem}.png").exists():
                        rows[r["image_id"]] = r
                except (ValueError, KeyError):
                    pass                               # a half-written last line from an interrupted run
            if rows:
                print(f"Resuming: {len(rows)} images already done.")

    files = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in EXTS)
    if a.limit:
        files = files[:a.limit]
    if not files:
        raise SystemExit(f"No images in {a.images}")
    todo = [p for p in files if p.name not in rows]
    if done_f.exists() and not todo:
        print(f"{out} is already complete for all {len(files)} images ({recipe}). Nothing to do (use --overwrite to rebuild).")
        return
    if done_f.exists():
        print(f"Cache was complete for {len(rows)} images; adding {len(todo)} new image(s).")
    with open(prog_f, "a", encoding="utf-8") as log:
        for i, p in enumerate(todo, 1):
            with Image.open(p) as im:
                rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
            les = None if a.no_lesion else detect_lesion(rgb)
            r = preprocess(rgb, a.size, lesion=les, enhance=not a.no_enhance, remove_hair_artifacts=not a.no_hair_removal, roi_min_frac=a.roi_min_frac)
            tmp = out / f"{p.stem}.tmp.png"                # write then rename: an interruption never leaves a corrupt crop
            cv2.imwrite(str(tmp), cv2.cvtColor(r.preview_rgb, cv2.COLOR_RGB2BGR))
            os.replace(tmp, out / f"{p.stem}.png")
            row = {"image_id": p.name, **({} if les is None else {k: v for k, v in les.info().items() if k != "other_boxes"})}
            rows[p.name] = row
            log.write(json.dumps(row) + "\n"); log.flush()
            if i % 200 == 0:
                print(f"  {len(rows)}/{len(files)}")

    df = pd.DataFrame([rows[p.name] for p in files])
    df.to_csv(out / "lesions.csv", index=False)
    done_f.write_text(recipe + "\n")
    prog_f.unlink(missing_ok=True); rec_f.unlink(missing_ok=True)
    print(f"Source folder has {len(files)} images; cache now holds {len(df)} crops.")
    if "found" in df:
        print(f"{len(df)} crops written to {out}. Lesion located in {df.found.mean() * 100:.1f}% (median area {df.area_fraction[df.found].median() * 100:.1f}% of the photo, "
              f"{(df.lesion_count > 1).mean() * 100:.1f}% with more than one spot).")
    else:
        print(f"{len(df)} crops written to {out} ({recipe}).")


if __name__ == "__main__":
    main()