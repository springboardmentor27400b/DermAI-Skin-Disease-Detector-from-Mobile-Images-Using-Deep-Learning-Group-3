"""Class definitions per dataset. See docs/dataset_selection.md."""

HAM10000_CLASSES = {
    "akiec": "Actinic keratosis / Bowen's disease",
    "bcc": "Basal cell carcinoma",
    "bkl": "Benign keratosis-like lesion",
    "df": "Dermatofibroma",
    "mel": "Melanoma",
    "nv": "Melanocytic nevus",
    "vasc": "Vascular lesion",
}
PAD_UFES_20_CLASSES = {
    "ACK": "Actinic keratosis",
    "BCC": "Basal cell carcinoma",
    "MEL": "Melanoma",
    "NEV": "Melanocytic nevus",
    "SCC": "Squamous cell carcinoma (incl. Bowen's disease)",
    "SEK": "Seborrheic keratosis",
}
CLASS_SETS = {"ham10000": HAM10000_CLASSES, "pad-ufes-20": PAD_UFES_20_CLASSES}

# Approximate mapping for cross-dataset testing (train HAM10000 -> test PAD-UFES-20).
# Approximate because label definitions differ; SCC has no HAM10000 class (akiec only covers in-situ disease).
PAD_TO_HAM = {"ACK": "akiec", "BCC": "bcc", "MEL": "mel", "NEV": "nv", "SEK": "bkl", "SCC": None}

# Published HAM10000 counts, used only by make_demo_metadata.py.
HAM10000_COUNTS = {"nv": 6705, "mel": 1113, "bkl": 1099, "bcc": 514, "akiec": 327, "vasc": 142, "df": 115}


def class_order(dataset: str) -> list[str]:
    return list(CLASS_SETS[dataset])


def class_to_idx(dataset: str) -> dict[str, int]:
    return {c: i for i, c in enumerate(class_order(dataset))}


# Backwards-compatible names (HAM10000)
CLASS_ORDER = class_order("ham10000")
CLASS_TO_IDX = class_to_idx("ham10000")

