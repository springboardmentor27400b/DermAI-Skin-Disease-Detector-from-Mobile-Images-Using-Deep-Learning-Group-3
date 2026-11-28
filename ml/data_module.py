"""Dataset over cached ROI crops (see precompute_rois.py) + split resolution from the Milestone 1 CSVs."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.preprocessing.pipeline import IMAGENET_MEAN, IMAGENET_STD, model_input   # noqa: E402

from classes import class_order    # noqa: E402

DATASET = "pad-ufes-20"


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"img_id": "image_id", "diagnostic": "label"}).copy()
    classes = class_order(DATASET)
    df["label"] = df["label"].astype(str).str.upper().replace({"BOD": "SCC"})
    df = df[df["label"].isin(classes)].copy()
    df["label_idx"] = df["label"].map({c: i for i, c in enumerate(classes)})
    if "group_id" not in df:
        df["group_id"] = df["patient_id"] if "patient_id" in df else df["image_id"]
    return df.reset_index(drop=True)


def resolve_splits(folds_csv: str | None, splits_dir: str | None, fold: int, final: bool = False):
    """Returns (train, val, test) DataFrames. test is None when final=True.
    Folds: test = fold k, val = fold (k+1) mod K, train = the rest (all patient-grouped by prepare_dataset.py)."""
    if folds_csv:
        df = _norm_cols(pd.read_csv(folds_csv))
        K = int(df["fold"].max()) + 1
        val_f = (fold + 1) % K
        if final:     # deployment model: every fold except one used for early stopping
            return df[df.fold != val_f], df[df.fold == val_f], None
        return df[~df.fold.isin([fold, val_f])], df[df.fold == val_f], df[df.fold == fold]
    d = Path(splits_dir)
    return tuple(_norm_cols(pd.read_csv(d / f"{n}.csv")) for n in ("train", "val", "test"))


class RoiDataset(Dataset):
    def __init__(self, df: pd.DataFrame, cache: str, train: bool, size: int = 224, aug: str = "basic"):
        self.df, self.cache, self.size = df.reset_index(drop=True), Path(cache), size
        paths = [self.cache / f"{Path(i).stem}.png" for i in self.df.image_id]
        missing = [p.name for p in paths if not p.exists()]
        if missing:
            raise SystemExit(f"{len(missing)} cached ROI crops missing in {self.cache} (e.g. {missing[:3]}). Run precompute_rois.py first. If it already ran, those source photos are probably missing from the --images folder (a cache only holds crops of photos that exist there).")
        self.paths, self.train = paths, train
        self.tf = build_train_transform(size, aug) if train else None

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        img = Image.open(self.paths[i]).convert("RGB")
        y = int(self.df.label_idx.iloc[i])
        if self.train:
            return self.tf(img), y
        return torch.from_numpy(model_input(np.asarray(img), self.size)), y


class Rot90:
    def __call__(self, img):
        return img.rotate(90 * int(torch.randint(0, 4, (1,))))


def build_train_transform(size: int, aug: str):
    ops = [T.RandomResizedCrop(size, scale=(0.65, 1.0), ratio=(0.9, 1.1)), T.RandomHorizontalFlip(), T.RandomVerticalFlip(), Rot90()]
    if aug == "strong":
        ops.append(T.TrivialAugmentWide())
    ops += [T.ColorJitter(0.2, 0.2, 0.1, 0.02), T.RandomApply([T.GaussianBlur(5, (0.1, 1.5))], p=0.2),   # blur mimics shaky phone shots
            T.ToTensor(), T.Normalize(IMAGENET_MEAN.tolist(), IMAGENET_STD.tolist())]
    return T.Compose(ops)

