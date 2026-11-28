"""Initial preprocessing pipeline.

Raw image -> EXIF orientation fix -> RGB -> centre square crop (ROI placeholder)
-> resize -> denoise -> gray-world colour normalisation -> CLAHE contrast
-> mild sharpen -> (preview uint8) -> ImageNet normalisation -> CHW float32.

Lesion-aware ROI cropping replaces the centre crop in Milestone 2.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

# Bump whenever preprocessing, hair removal or lesion detection changes. ml/precompute_rois.py stamps it on every cache,
# train.py copies it into the model, and ml/export_model.py refuses to deploy a model trained on a different version.
PIPELINE_VERSION = "m2.2"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class PreprocessResult:
    preview_rgb: np.ndarray            # HxWx3 uint8, for display/storage
    model_input: np.ndarray            # 3xHxW float32, normalised
    steps: list[str] = field(default_factory=list)


def to_rgb_array(img: Image.Image) -> np.ndarray:
    """Apply EXIF orientation (phones store rotation as metadata) and return RGB uint8."""
    img = ImageOps.exif_transpose(img)
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def center_square_crop(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    s = min(h, w)
    y0, x0 = (h - s) // 2, (w - s) // 2
    return rgb[y0:y0 + s, x0:x0 + s]


def gray_world(rgb: np.ndarray) -> np.ndarray:
    """Simple colour-constancy: scale channels so their means match."""
    f = rgb.astype(np.float32)
    means = f.reshape(-1, 3).mean(axis=0)
    gain = means.mean() / np.maximum(means, 1e-6)
    return np.clip(f * gain, 0, 255).astype(np.uint8)


def clahe_on_lightness(rgb: np.ndarray, clip: float = 2.0) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)


def unsharp(rgb: np.ndarray, amount: float = 0.4) -> np.ndarray:
    blur = cv2.GaussianBlur(rgb, (0, 0), 1.2)
    return cv2.addWeighted(rgb, 1 + amount, blur, -amount, 0)


def normalize(rgb: np.ndarray) -> np.ndarray:
    x = rgb.astype(np.float32) / 255.0
    x = (x - IMAGENET_MEAN) / IMAGENET_STD
    return np.ascontiguousarray(x.transpose(2, 0, 1))


def preprocess(rgb: np.ndarray, size: int = 224, lesion=None, enhance: bool = True, remove_hair_artifacts: bool = True, roi_min_frac: float = 0.3) -> PreprocessResult:
    """lesion: optional LesionResult. When it was found the crop is the lesion ROI (with context), otherwise the centre square.
    enhance=False skips denoise / colour normalisation / CLAHE / sharpen (for ablations)."""
    steps = ["exif_orientation", "rgb"]
    if lesion is not None and lesion.found:
        from app.preprocessing.lesion import roi_square
        x0, y0, side = roi_square(lesion, rgb.shape[:2], min_frac=roi_min_frac)   # larger min = closer to the whole photo
        x = rgb[y0:y0 + side, x0:x0 + side]; steps.append("lesion_roi_crop")
    else:
        x = center_square_crop(rgb); steps.append("center_square_crop")
    x = cv2.resize(x, (size, size), interpolation=cv2.INTER_AREA); steps.append(f"resize_{size}")
    if remove_hair_artifacts:
        from app.preprocessing.hair import remove_hair
        x, _ = remove_hair(x, work=size); steps.append("hair_removal")
    if enhance:
        x = cv2.fastNlMeansDenoisingColored(x, None, 3, 3, 5, 15); steps.append("denoise_nlm")
        x = gray_world(x); steps.append("gray_world_color_norm")
        x = clahe_on_lightness(x); steps.append("clahe_contrast")
        x = unsharp(x); steps.append("unsharp_mask")
    return PreprocessResult(preview_rgb=x, model_input=normalize(x), steps=steps + ["imagenet_normalize"])


def model_input(rgb: np.ndarray, size: int = 224, mean=IMAGENET_MEAN, std=IMAGENET_STD) -> np.ndarray:
    """The single eval-time transform shared by training (ml/) and the API: resize, scale, normalise -> CHW float32."""
    x = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA) if rgb.shape[:2] != (size, size) else rgb
    x = (x.astype(np.float32) / 255.0 - np.asarray(mean, np.float32)) / np.asarray(std, np.float32)
    return np.ascontiguousarray(x.transpose(2, 0, 1))


def save_preview(rgb: np.ndarray, path: str) -> None:
    Image.fromarray(rgb).save(path, format="PNG")

