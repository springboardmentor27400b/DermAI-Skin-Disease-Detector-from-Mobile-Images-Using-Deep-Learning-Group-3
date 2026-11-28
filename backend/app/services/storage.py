import os
import re
import uuid
from pathlib import Path

from app.core.config import settings


def _ext_for(fmt: str) -> str:
    return {"JPEG": ".jpg", "PNG": ".png"}.get(fmt.upper(), ".bin")


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "upload")
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:120] or "upload"


def save_original(case_id: int, data: bytes, fmt: str) -> str:
    folder = Path(settings.upload_dir) / f"case_{case_id}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{_ext_for(fmt)}"
    path.write_bytes(data)
    return str(path)


def processed_path_for(case_id: int) -> str:
    folder = Path(settings.processed_dir) / f"case_{case_id}"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / f"{uuid.uuid4().hex}.png")


def remove_files(*paths: str | None) -> None:
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def lesion_path_for(case_id: int) -> str:
    folder = Path(settings.processed_dir) / f"case_{case_id}"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / f"{uuid.uuid4().hex}_lesion.png")


def saliency_path_for(case_id: int) -> str:
    folder = Path(settings.processed_dir) / f"case_{case_id}"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / f"{uuid.uuid4().hex}_sal.png")


def cam_path_for(case_id: int) -> str:
    folder = Path(settings.processed_dir) / f"case_{case_id}"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / f"{uuid.uuid4().hex}_cam.png")

