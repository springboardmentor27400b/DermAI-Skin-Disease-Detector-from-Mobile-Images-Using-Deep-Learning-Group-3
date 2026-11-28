"""Train several architectures over every fold, one after another (resumable: finished runs are skipped).

    python run_experiments.py --archs simple_cnn,resnet50,densenet121,efficientnet_b0,mobilenet_v3_large,convnext_tiny \
        --folds data/splits_v2/folds.csv --cache data/pad_ufes_20/roi256 --out runs/m2 --epochs 30
Extra arguments after `--` go to train.py, e.g.  -- --imbalance focal
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archs", required=True)
    ap.add_argument("--folds", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--only-folds", default=None, help="comma list, e.g. 0,1 for a quick trial")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a, extra = ap.parse_known_args()
    extra = [e for e in extra if e != "--"]
    folds = [int(f) for f in a.only_folds.split(",")] if a.only_folds else range(a.n_folds)
    for arch in a.archs.split(","):
        for k in folds:
            out = Path(a.out) / arch / f"fold{k}"
            if (out / "metrics.json").exists():
                print(f"skip {arch} fold{k} (done)"); continue
            cmd = [sys.executable, "train.py", "--arch", arch, "--folds", a.folds, "--fold", str(k), "--cache", a.cache,
                   "--out", str(out), "--epochs", str(a.epochs), "--resume", *extra]
            print(">>", " ".join(cmd))
            if not a.dry_run:
                subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()

