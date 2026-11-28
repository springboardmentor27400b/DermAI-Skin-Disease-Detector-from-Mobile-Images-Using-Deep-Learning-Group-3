"""Dataset definitions and a loader that normalises them to one schema.

Primary dataset: PAD-UFES-20 (smartphone photos). HAM10000 (dermoscopic) is supported for optional pre-training.
Columns returned by load(): image_id, patient_id, lesion_id, group_id, label, and (when present)
age, sex, site, fitzpatrick, biopsied.  `group_id` is what splits must keep together.
"""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Spec:
    key: str
    title: str
    image_col: str
    label_col: str
    classes: dict[str, str]
    patient_col: str | None = None
    lesion_col: str | None = None
    age_col: str | None = None
    sex_col: str | None = None
    site_col: str | None = None
    fitzpatrick_col: str | None = None
    biopsy_col: str | None = None
    aliases: dict[str, str] = field(default_factory=dict)   # label merges, e.g. Bowen's disease -> SCC
    default_metadata: str = "metadata.csv"


PAD_UFES_20 = Spec(
    key="pad_ufes_20", title="PAD-UFES-20 (smartphone images)",
    image_col="img_id", patient_col="patient_id", lesion_col="lesion_id", label_col="diagnostic",
    age_col="age", sex_col="gender", site_col="region", fitzpatrick_col="fitspatrick", biopsy_col="biopsed",
    classes={
        "ACK": "Actinic keratosis",
        "BCC": "Basal cell carcinoma",
        "MEL": "Melanoma",
        "NEV": "Melanocytic nevus",
        "SCC": "Squamous cell carcinoma (includes Bowen's disease)",
        "SEK": "Seborrheic keratosis",
    },
    aliases={"BOD": "SCC"},
)

HAM10000 = Spec(
    key="ham10000", title="HAM10000 (dermoscopic images)",
    image_col="image_id", lesion_col="lesion_id", label_col="dx",
    age_col="age", sex_col="sex", site_col="localization",
    classes={
        "akiec": "Actinic keratosis / Bowen's disease", "bcc": "Basal cell carcinoma", "bkl": "Benign keratosis-like lesion",
        "df": "Dermatofibroma", "mel": "Melanoma", "nv": "Melanocytic nevus", "vasc": "Vascular lesion",
    },
    default_metadata="HAM10000_metadata.csv",
)

SPECS = {s.key: s for s in (PAD_UFES_20, HAM10000)}
IMAGE_EXTS = (".png", ".jpg", ".jpeg")

# The same field is called different things in different copies of a dataset; accept either.
_SYNONYMS = [("img_id", "image_id"), ("diagnostic", "dx"), ("region", "localization"),
             ("fitspatrick", "fitzpatrick"), ("gender", "sex"), ("biopsed", "biopsied")]


def _find(columns, name: str | None) -> str | None:
    if name is None:
        return None
    group = next((g for g in _SYNONYMS if name in g), (name,))
    return next((c for c in group if c in columns), None)


def load(spec: Spec, metadata_path: str | Path) -> pd.DataFrame:
    path = Path(metadata_path)
    if not path.is_file():
        data = Path.cwd() / "data"
        found = [str(p.relative_to(Path.cwd())) for p in sorted(data.rglob("*.csv"))[:12]] if data.is_dir() else []
        raise SystemExit(
            f"Metadata file not found: {path.resolve()}\n"
            f"Run this from the ml folder (current folder: {Path.cwd()}).\n"
            + (f"CSV files under data/ :\n  " + "\n  ".join(found) + "\nUse one of these as --metadata." if found
               else "There are no CSV files under ml/data/ yet. Copy the dataset's metadata.csv there (see ml/README.md)."))
    raw = pd.read_csv(path)
    raw.columns = [c.strip() for c in raw.columns]
    cols = set(raw.columns)
    col = lambda name: _find(cols, name)
    missing = [n for n in (spec.image_col, spec.label_col) if col(n) is None]
    if missing:
        raise SystemExit(f"{metadata_path} has no column for {missing} (also tried common alternatives).\n"
                         f"Columns found: {list(raw.columns)}\nIs --dataset {spec.key} the right choice for this file?")

    def text(name: str) -> pd.Series:
        """Trimmed strings with real missing values kept as <NA> (never the text 'nan')."""
        return raw[col(name)].astype("string").str.strip().replace("", pd.NA)

    df = pd.DataFrame({"image_id": text(spec.image_col)})
    known = {c.lower(): c for c in spec.classes}
    aliases = {k.lower(): v.lower() for k, v in spec.aliases.items()}
    shown = text(spec.label_col)
    key = shown.str.lower().map(lambda v: aliases.get(v, v) if isinstance(v, str) else v)
    df["label"] = key.map(lambda v: known.get(v) if isinstance(v, str) else None)
    df.attrs["unknown_labels"] = sorted({v for v, k in zip(shown.dropna(), key.dropna()) if k not in known})

    if df["label"].isna().mean() > 0.5:
        raise SystemExit(f"Most labels in {metadata_path} are not valid {spec.title} classes {list(spec.classes)}.\n"
                         f"Labels found: {sorted(set(shown.dropna()))[:12]}\nIs --dataset {spec.key} the right choice for this file?")

    has = lambda name: col(name) is not None
    df["patient_id"] = text(spec.patient_col) if has(spec.patient_col) else None
    if has(spec.lesion_col):
        lesion = text(spec.lesion_col)
        # lesion numbers can repeat across patients, so a lesion is identified by patient + lesion number
        df["lesion_id"] = (df["patient_id"] + "_" + lesion) if df["patient_id"] is not None and not lesion.str.startswith("PAT_", na=False).any() else lesion
    else:
        df["lesion_id"] = None
    # Images of one patient (or, lacking patient ids, one lesion) must never straddle train and test.
    df["group_id"] = df["patient_id"] if has(spec.patient_col) else df["lesion_id"] if has(spec.lesion_col) else df["image_id"]

    if has(spec.age_col):
        df["age"] = pd.to_numeric(raw[col(spec.age_col)], errors="coerce")
    if has(spec.sex_col):
        df["sex"] = text(spec.sex_col).str.lower()
    if has(spec.site_col):
        df["site"] = text(spec.site_col).str.lower()
    if has(spec.fitzpatrick_col):
        f = pd.to_numeric(raw[col(spec.fitzpatrick_col)], errors="coerce")
        df["fitzpatrick"] = f.map(lambda v: None if pd.isna(v) else str(int(v)))
    if has(spec.biopsy_col):
        df["biopsied"] = text(spec.biopsy_col).str.lower().map({"true": True, "false": False, "1": True, "0": False}).astype("object")
    return df


def resolve_image(images_dir: Path, image_id: str) -> Path | None:
    p = images_dir / image_id
    if p.suffix.lower() in IMAGE_EXTS:
        return p if p.exists() else None
    for ext in IMAGE_EXTS:
        if (images_dir / f"{image_id}{ext}").exists():
            return images_dir / f"{image_id}{ext}"
    return None

