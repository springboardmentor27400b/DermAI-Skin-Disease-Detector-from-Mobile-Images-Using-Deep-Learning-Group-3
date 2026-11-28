"""Write a SYNTHETIC metadata file shaped like the real one, to try the scripts before the dataset is in place.
Class counts follow the PAD-UFES-20 paper; every other value is random. Never report results from it."""
import argparse

import numpy as np
import pandas as pd

PAD_COUNTS = {"BCC": 845, "ACK": 730, "NEV": 244, "SEK": 235, "SCC": 192, "MEL": 52}
HAM_COUNTS = {"nv": 6705, "mel": 1113, "bkl": 1099, "bcc": 514, "akiec": 327, "vasc": 142, "df": 115}
REGIONS = ["ARM", "NECK", "FACE", "HAND", "FOREARM", "CHEST", "NOSE", "THIGH", "BACK", "LIP", "FOOT", "ABDOMEN", "EAR", "SCALP"]


def pad(rng) -> pd.DataFrame:
    rows, patient, lesion = [], 0, 0
    for dx, n in PAD_COUNTS.items():
        i = 0
        while i < n:
            patient += 1
            for _ in range(int(rng.choice([1, 1, 2, 3]))):          # lesions per patient
                lesion += 1
                for _ in range(min(n - i, int(rng.choice([1, 1, 2])))):  # photos per lesion
                    rows.append(dict(patient_id=f"PAT_{patient}", lesion_id=lesion, img_id=f"PAT_{patient}_{lesion}_{len(rows)}.png",
                                     diagnostic=dx, age=int(np.clip(rng.normal(60, 15), 6, 95)) if rng.random() > .02 else np.nan,
                                     gender=rng.choice(["FEMALE", "MALE"]), region=rng.choice(REGIONS),
                                     fitspatrick=rng.choice([1., 2., 3., 4., np.nan], p=[.1, .35, .2, .02, .33]),
                                     biopsed=bool(dx in ("BCC", "SCC", "MEL") or rng.random() < .3)))
                    i += 1
                    if i >= n:
                        break
                if i >= n:
                    break
    return pd.DataFrame(rows)


def ham(rng) -> pd.DataFrame:
    rows, lesion = [], 0
    for dx, n in HAM_COUNTS.items():
        i = 0
        while i < n:
            lesion += 1
            for _ in range(min(n - i, int(rng.choice([1, 1, 2, 3])))):
                rows.append(dict(lesion_id=f"HAM_{lesion:07d}", image_id=f"ISIC_{len(rows):07d}", dx=dx, age=float(np.clip(rng.normal(52, 17), 5, 85)),
                                 sex=rng.choice(["male", "female"]), localization=rng.choice(["back", "trunk", "face", "foot"])))
                i += 1
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["pad_ufes_20", "ham10000"], default="pad_ufes_20")
    ap.add_argument("--out", default="data/demo_metadata.csv")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    df = (pad if a.dataset == "pad_ufes_20" else ham)(rng).sample(frac=1, random_state=a.seed)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df)} SYNTHETIC rows -> {a.out}")

