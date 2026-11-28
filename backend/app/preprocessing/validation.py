"""Upload validation: format, file size, resolution, decodability."""
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.core.config import settings


class ImageValidationError(ValueError):
    """Raised when an upload cannot be accepted for analysis."""


@dataclass
class ValidatedImage:
    image: Image.Image
    format: str
    width: int
    height: int
    size_bytes: int


def validate_image_bytes(data: bytes) -> ValidatedImage:
    size = len(data)
    if size == 0:
        raise ImageValidationError("The file is empty.")
    if size > settings.max_upload_mb * 1024 * 1024:
        raise ImageValidationError(f"File is larger than {settings.max_upload_mb} MB.")

    try:
        probe = Image.open(BytesIO(data))
        fmt = (probe.format or "").upper()
        probe.verify()                       # integrity check (invalidates the handle)
        img = Image.open(BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ImageValidationError("The file is not a readable image.")

    if fmt not in settings.allowed_formats:
        raise ImageValidationError(
            f"Unsupported format '{fmt or 'unknown'}'. Allowed: {', '.join(settings.allowed_formats)}."
        )

    w, h = img.size
    if min(w, h) < settings.min_resolution:
        raise ImageValidationError(
            f"Resolution {w}x{h} is too low; the shorter side must be at least {settings.min_resolution}px."
        )
    return ValidatedImage(image=img, format=fmt, width=w, height=h, size_bytes=size)

