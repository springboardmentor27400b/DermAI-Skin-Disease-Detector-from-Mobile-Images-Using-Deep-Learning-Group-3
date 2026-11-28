"""Contact sheets for judging quality thresholds by eye.

Run quality_audit.py first, then:
    python quality_review.py --images data/pad_ufes_20/images --by blur
    python quality_review.py --images data/pad_ufes_20/images --by contrast

For each percentile band it writes one sheet of evenly spaced examples with their scores. Look at them in order:
the lowest band should look clearly unusable, the middle band borderline, and the top bands fine. If the lowest
band still looks fine, the 'poor' cut-off is too strict; if the middle band looks clearly bad, it is too lenient.
"""
import argparse
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageOps

THUMB, COLS = 200, 6


def sheet(rows: pd.DataFrame, folder: Path, by: str, title: str, path: Path) -> None:
    n = len(rows)
    nrows = (n + COLS - 1) // COLS
    canvas = Image.new("RGB", (COLS * THUMB, nrows * (THUMB + 18) + 30), "white")
    d = ImageDraw.Draw(canvas)
    d.text((6, 8), title, fill="black")
    for i, (_, r) in enumerate(rows.iterrows()):
        x, y = (i % COLS) * THUMB, 30 + (i // COLS) * (THUMB + 18)
        with Image.open(folder / r.file) as im:
            t = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), (THUMB - 4, THUMB - 4))
        canvas.paste(t, (x + 2, y + 2))
        d.text((x + 4, y + THUMB), f"{by} {r[by]:.0f}  [{r.label}]", fill="black")
    canvas.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--scores", default="reports/quality/quality_scores.csv")
    ap.add_argument("--by", choices=["blur", "contrast"], default="blur")
    ap.add_argument("--bands", default="0-5,5-25,25-50,75-100", help="percentile bands, e.g. 0-5,5-25")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--out", default="reports/quality/review")
    a = ap.parse_args()

    df = pd.read_csv(a.scores).sort_values(a.by).reset_index(drop=True)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for band in a.bands.split(","):
        lo, hi = (float(x) for x in band.split("-"))
        sub = df.iloc[int(len(df) * lo / 100): max(int(len(df) * hi / 100), int(len(df) * lo / 100) + 1)]
        pick = sub.iloc[[int(i * (len(sub) - 1) / max(a.n - 1, 1)) for i in range(min(a.n, len(sub)))]]
        name = out / f"{a.by}_p{band.replace('-', '_to_')}.png"
        sheet(pick, Path(a.images), a.by, f"{a.by}: percentile {band} ({a.by} {sub[a.by].min():.0f} to {sub[a.by].max():.0f})", name)
        print("wrote", name)


if __name__ == "__main__":
    main()

