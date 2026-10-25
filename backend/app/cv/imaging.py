"""Image I/O and normalization helpers built on OpenCV 5."""

from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np

from ..config import settings

ACCEPTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


class ImageValidationError(ValueError):
    """Raised when an uploaded/generated image fails validation."""


def load_bgr(path: str | Path) -> np.ndarray:
    """Read an image from disk, raising a typed error if unreadable."""
    path = Path(path)
    if not path.exists():
        raise ImageValidationError(f"image not found: {path}")
    data = np.fromfile(str(path), dtype=np.uint8)  # unicode-safe on Windows
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ImageValidationError(f"unreadable or corrupt image: {path.name}")
    return img


def decode_bgr(data: bytes, name: str = "upload") -> np.ndarray:
    if len(data) == 0:
        raise ImageValidationError(f"empty image payload: {name}")
    if len(data) > settings.max_upload_bytes:
        raise ImageValidationError(f"image too large ({len(data)} bytes, limit {settings.max_upload_bytes})")
    arr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ImageValidationError(f"unsupported or corrupt image: {name}")
    h, w = arr.shape[:2]
    if max(h, w) > settings.max_image_dim_px:
        raise ImageValidationError(f"image dimensions {w}x{h} exceed limit {settings.max_image_dim_px}px")
    if min(h, w) < 64:
        raise ImageValidationError(f"image too small ({w}x{h}); minimum dimension is 64px")
    return arr


def save_png(img: np.ndarray, path: str | Path) -> str:
    """Write a PNG artifact and return the absolute path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError(f"PNG encode failed for {path}")
    buf.tofile(str(path))
    return str(path)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def normalize_orientation(img: np.ndarray) -> np.ndarray:
    """Normalizations that must happen before any comparison.

    OpenCV loads channels BGR; we standardize on that everywhere. EXIF rotation
    is not present in OpenCV-decoded buffers, and the demo data is generated
    upright, so this is a documented no-op that exists as the single place to
    extend (e.g. for camera captures with EXIF).
    """
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def crop_clamped(img: np.ndarray, x: int, y: int, w: int, h: int, pad: int = 0) -> np.ndarray:
    """Crop with clamping and optional symmetric padding in source pixels."""
    H, W = img.shape[:2]
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(W, x + w + pad)
    y1 = min(H, y + h + pad)
    if x1 - x0 < 2 or y1 - y0 < 2:
        # region degenerated to nothing (should not happen); return 2x2 corner
        x0, y0, x1, y1 = 0, 0, min(2, W), min(2, H)
    return img[y0:y1, x0:x1]


def encode_data_url(img: np.ndarray, quality: int = 88) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def artifact_png_url(name: str) -> str:
    return f"/api/inspections/run-artifact?path={name}"
