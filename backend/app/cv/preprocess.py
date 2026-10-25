"""Stage 2 — preprocessing.

Design rule: preprocessing exists to make *registration* robust. The diff-based
defect detector runs on lightly-denoised grayscale so that small defect
evidence (pinholes, spurs) is not smoothed away. Every transform is
configurable and recorded in the inspection trace.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import cv2
import numpy as np


@dataclass
class PreprocessParams:
    """All values logged with the inspection for reproducibility."""

    clahe_clip_limit: float = 2.0
    clahe_grid: int = 8
    median_ksize: int = 3          # odd, >=1 disables when 1
    use_clahe_for_registration: bool = True
    use_clahe_for_detection: bool = False  # CLAHE can amplify illumination edges

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def preprocess(
    gray: np.ndarray,
    params: PreprocessParams | None = None,
    *,
    for_registration: bool = True,
) -> np.ndarray:
    """Grayscale (already) -> optional CLAHE -> optional median filter.

    Returns uint8 single-channel image of the same size.
    """
    p = params or PreprocessParams()
    out = gray
    if out.dtype != np.uint8:
        out = np.clip(out, 0, 255).astype(np.uint8)
    use_clahe = p.use_clahe_for_registration if for_registration else p.use_clahe_for_detection
    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=p.clahe_clip_limit, tileGridSize=(p.clahe_grid, p.clahe_grid))
        out = clahe.apply(out)
    if p.median_ksize and p.median_ksize > 1:
        out = cv2.medianBlur(out, p.median_ksize)
    return out
