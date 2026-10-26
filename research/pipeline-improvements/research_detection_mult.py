"""Stage 4 — defect candidate detection on an aligned reference/test pair.

Method (all OpenCV, no learned model):
  1. absdiff between reference and aligned test (light denoise only, so small
     defects survive).
  2. local normalized cross-correlation (NCC) map computed with box filters —
     invariant to gain/bias illumination change, so glare/shadow raise the
     diff map but *not* the structural mismatch map. This separation is what
     the agent later exploits to reject illumination confounds.
  3. candidate mask = (diff > adaptive threshold) AND (mismatch > gate),
     morphological cleanup, connected components.
  4. per-component evidence measurements + named heuristic scores.

All scores are heuristic quality measures (documented), not probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from ..config import settings
from .imaging import crop_clamped


@dataclass
class DetectionParams:
    min_mean_diff: float = 10.0        # 0..255 — below this a component is noise
    min_structural_mismatch: float = 0.25   # 1-NCC gate for accepting a component
    diff_percentile: float = 97.0      # adaptive floor on the diff map
    morph_open_ksize: int = 3
    morph_close_ksize: int = 5
    morph_bridge_ksize: int = 17       # bridges fragments across excluded (saturated) gaps
    ncc_window: int = 15
    dilate_px: int = 2                 # bbox padding around masks

    def as_dict(self) -> dict:
        return {
            "min_mean_diff": self.min_mean_diff,
            "min_structural_mismatch": self.min_structural_mismatch,
            "diff_percentile": self.diff_percentile,
            "morph_open_ksize": self.morph_open_ksize,
            "morph_close_ksize": self.morph_close_ksize,
            "morph_bridge_ksize": self.morph_bridge_ksize,
            "ncc_window": self.ncc_window,
        }


@dataclass
class DetectionResult:
    candidates: list[dict] = field(default_factory=list)
    diff_map: np.ndarray | None = None
    mismatch_map: np.ndarray | None = None
    candidate_mask: np.ndarray | None = None
    params: dict = field(default_factory=dict)


def local_ncc(ref: np.ndarray, test: np.ndarray, window: int = 15) -> np.ndarray:
    """Per-pixel normalized cross-correlation over a square window.

    Computed with box filters (integral-image speed). Returns float32 in [-1, 1].
    """
    r = ref.astype(np.float32)
    t = test.astype(np.float32)
    k = (window, window)
    mr = cv2.boxFilter(r, -1, k, anchor=(-1, -1), normalize=True)
    mt = cv2.boxFilter(t, -1, k, anchor=(-1, -1), normalize=True)
    rr = cv2.boxFilter(r * r, -1, k, anchor=(-1, -1), normalize=True)
    tt = cv2.boxFilter(t * t, -1, k, anchor=(-1, -1), normalize=True)
    rt = cv2.boxFilter(r * t, -1, k, anchor=(-1, -1), normalize=True)
    var_r = np.maximum(rr - mr * mr, 0)
    var_t = np.maximum(tt - mt * mt, 0)
    cov = rt - mr * mt
    denom = np.sqrt(var_r * var_t) + 1e-6
    ncc = cov / denom
    return np.clip(ncc, -1.0, 1.0)


def detect_candidates(
    ref_gray: np.ndarray,
    aligned_test_gray: np.ndarray,
    valid_mask: np.ndarray | None,
    params: DetectionParams | None = None,
) -> DetectionResult:
    p = params or DetectionParams()
    H, W = ref_gray.shape[:2]

    # Mean-transfer illumination normalization: align the test image's local
    # means to the reference's at a large scale. Removes smooth gain drift,
    # shadows and glare blobs while preserving defect magnitudes absolutely.
    # (Local variance matching was tried and rejected: noise-driven gain
    # fluctuation multiplied into structured areas and created residue.)
    norm_sigma = 61
    ref_f = ref_gray.astype(np.float32)
    test_f = aligned_test_gray.astype(np.float32)
    mean_ref = cv2.GaussianBlur(ref_f, (0, 0), norm_sigma)
    mean_test = cv2.GaussianBlur(test_f, (0, 0), norm_sigma)
    test_norm = test_f * np.clip((mean_ref+1.0)/(mean_test+1.0), 0.5, 2.0)
    work_ref = ref_f
    work_test = test_norm
    diff = np.abs(work_ref - work_test)

    # Observation validity: pixels at the rails are saturated/clipped (glare,
    # shadow) — the clip knee is a nonlinear edge that no smooth illumination
    # model removes, so exclude them and a wide halo from detection entirely.
    obs_valid = ((aligned_test_gray < 250) & (aligned_test_gray > 5)).astype(np.uint8) * 255
    obs_valid = cv2.dilate(obs_valid, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))

    # illumination-robust structural mismatch; windows with essentially no
    # reference structure carry no evidence, so their mismatch is zeroed.
    ncc = local_ncc(ref_gray, aligned_test_gray, p.ncc_window)
    mean_r = cv2.boxFilter(ref_f, -1, (p.ncc_window, p.ncc_window))
    var_r = cv2.boxFilter((ref_f - mean_r) ** 2, -1, (p.ncc_window, p.ncc_window))
    structureless = (np.sqrt(var_r) < 5.0) | (np.sqrt(var_r) > 60.0)
    mismatch = np.where(structureless, 0.0, 1.0 - ncc).astype(np.float32)

    otsu_t, _ = cv2.threshold(np.clip(diff, 0, 255).astype(np.uint8), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    valid_pixels = diff[valid_mask > 0] if valid_mask is not None else diff.ravel()
    pct_t = float(np.percentile(valid_pixels, p.diff_percentile)) if valid_pixels.size else 255.0
    diff_t = max(otsu_t, pct_t, 10.0)

    base_mask = ((diff >= diff_t) & (mismatch >= p.min_structural_mismatch)).astype(np.uint8) * 255
    base_mask[obs_valid == 0] = 0
    # Added-material channel: catches copper ADDED on featureless background,
    # where the NCC gate is blind by construction (no reference structure to
    # mismatch against). Gate is relative — residual high-pass energy in the
    # normalized test must dominate the reference's — so structure near traces
    # does not disqualify, and smooth illumination residue does not qualify.
    k = (p.ncc_window, p.ncc_window)
    res_test = test_norm - mean_ref
    res_ref = ref_f - mean_ref
    std_test_hp = np.sqrt(cv2.boxFilter(res_test * res_test, -1, k))
    std_ref_hp = np.sqrt(cv2.boxFilter(res_ref * res_ref, -1, k))
    added_mask = ((diff >= diff_t) & (std_test_hp >= 6.0) & (std_test_hp >= 2.5 * (std_ref_hp + 1.0))).astype(np.uint8) * 255
    added_mask[obs_valid == 0] = 0
    mask = cv2.bitwise_or(base_mask, added_mask)
    if valid_mask is not None:
        mask[valid_mask == 0] = 0

    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (p.morph_open_ksize, p.morph_open_ksize))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (p.morph_close_ksize, p.morph_close_ksize))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open)
    # closing bridges fragments split by the saturation exclusion mask
    k_bridge = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (p.morph_bridge_ksize, p.morph_bridge_ksize))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_bridge)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    img_area = H * W
    max_area = img_area * settings.max_candidate_area_frac

    edge_ref = cv2.Canny(cv2.GaussianBlur(ref_gray, (3, 3), 0), 60, 140)
    edge_test = cv2.Canny(cv2.GaussianBlur(aligned_test_gray, (3, 3), 0), 60, 140)

    candidates: list[dict] = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < settings.min_candidate_area_px or area > max_area:
            continue
        comp = labels == i
        mean_diff = float(diff[comp].mean())
        max_diff = float(diff[comp].max())
        mean_mismatch = float(mismatch[comp].mean())
        if mean_diff < p.min_mean_diff:
            continue
        ref_under = float(ref_gray[comp].std()) + 1e-6
        test_under = float(aligned_test_gray[comp].std()) + 1e-6
        mean_delta = float(aligned_test_gray[comp].mean()) - float(ref_gray[comp].mean())
        added_on_flat = bool(ref_under < 8.0 and mean_delta > 20.0)

        cx, cy = centroids[i]
        ref_crop = crop_clamped(ref_gray, x, y, w, h, pad=4)
        test_crop = crop_clamped(aligned_test_gray, x, y, w, h, pad=4)
        local_contrast = float(ref_crop.std()) + 1e-6

        ec_ref = int((edge_ref[comp]).sum())
        ec_test = int((edge_test[comp]).sum())
        edge_delta = (ec_test - ec_ref) / max(ec_ref + ec_test, 1)

        touches_invalid = False
        if valid_mask is not None:
            touches_invalid = bool((valid_mask[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] == 0).any()
                                   and (valid_mask[y:y + h, x:x + w] == 0).any())

        # heuristic quality: strong local contrast + away from warp border = trustworthy
        evidence_quality = float(np.clip(local_contrast / 60.0, 0, 1))
        if touches_invalid:
            evidence_quality *= 0.3

        candidates.append({
            "bbox": [int(x), int(y), int(w), int(h)],
            "area_px": int(area),
            "centroid": [int(round(cx)), int(round(cy))],
            "difference_score": round(mean_diff / 255.0, 4),
            "max_diff": round(max_diff, 1),
            "structural_mismatch_score": round(float(np.clip(mean_mismatch, 0, 1)), 4),
            "evidence_quality_score": round(evidence_quality, 4),
            "local_contrast": round(local_contrast, 2),
            "edge_delta": round(float(edge_delta), 4),
            "touches_invalid_warp_region": touches_invalid,
            "added_on_flat_background": added_on_flat,
            "illumination_suspect": bool(mean_mismatch < 0.35 and mean_diff / 255.0 > 0.15 and not added_on_flat),
        })

    candidates.sort(key=lambda c: (-c["difference_score"] * c["structural_mismatch_score"], -c["area_px"]))
    return DetectionResult(
        candidates=candidates[: settings.max_candidates_tracked],
        diff_map=np.clip(diff, 0, 255).astype(np.uint8),
        mismatch_map=(np.clip(mismatch, 0, 1) * 255).astype(np.uint8),
        candidate_mask=mask,
        params=p.as_dict() | {"diff_threshold": round(float(diff_t), 2), "otsu_threshold": round(float(otsu_t), 2)},
    )


def diff_heatmap(diff_map: np.ndarray, valid_mask: np.ndarray | None = None) -> np.ndarray:
    """Color heatmap of the difference map for UI display (BGR)."""
    d = diff_map.copy()
    if valid_mask is not None:
        d[valid_mask == 0] = 0
    d = cv2.normalize(d, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.applyColorMap(d, cv2.COLORMAP_INFERNO)
