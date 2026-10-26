"""Stage 5 — targeted secondary inspection tools.

Each tool is a real OpenCV analysis over a region, chosen by the agent based on
observed evidence. Three honesty classes, surfaced in every result:

  reprocess      — recomputes existing pixels at higher scrutiny (adds *analysis*,
                   never new optical detail)
  alternate_view — reads a genuinely different, previously captured image
  request        — asks for new evidence that does not exist yet

Tool outcomes carry `supports_defect` (True/False) or None = inconclusive,
plus metrics that the verifier consumes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .detection import local_ncc
from .imaging import crop_clamped
from .registration import register

ECC_LOCAL_TERM = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-7)


@dataclass
class ToolOutcome:
    tool: str
    region_id: str
    summary: str
    metrics: dict[str, Any]
    supports_defect: bool | None
    evidence_kind: str
    honesty: str  # reprocess | alternate_view | request
    artifacts: dict[str, np.ndarray] = field(default_factory=dict)
    duration_s: float = 0.0


@dataclass
class ToolContext:
    """Per-inspection immutable evidence bundle handed to every tool call."""

    ref_gray: np.ndarray            # detection-preprocessed reference
    test_aligned: np.ndarray        # aligned test (detection preprocessing)
    test_original: np.ndarray       # aligned test with lighter processing
    valid_mask: np.ndarray | None
    diff_map: np.ndarray
    mismatch_map: np.ndarray
    secondary_view_gray: np.ndarray | None = None
    secondary_aligned: np.ndarray | None = None   # aligned secondary -> reference
    secondary_valid_mask: np.ndarray | None = None


def _pad_bbox(x: int, y: int, w: int, h: int, shape: tuple[int, int], pad: int = 8) -> tuple[int, int, int, int]:
    H, W = shape
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(W, x + w + pad)
    y1 = min(H, y + h + pad)
    return x0, y0, x1 - x0, y1 - y0


def _diff_stats(diff_crop: np.ndarray, mismatch_crop: np.ndarray) -> dict[str, float]:
    return {
        "mean_diff": round(float(diff_crop.mean()), 2),
        "max_diff": round(float(diff_crop.max()), 1),
        "mean_mismatch": round(float(mismatch_crop.mean()), 4),
        "changed_frac": round(float((diff_crop > 20).mean()), 4),
    }


def tool_highres_zoom(ctx: ToolContext, region_id: str, bbox: list[int]) -> ToolOutcome:
    """Reprocess the region at 4x magnification and recompute difference stats.

    Reprocessing of already-captured pixels — explicitly NOT a new observation.
    """
    t0 = time.perf_counter()
    x, y, w, h = _pad_bbox(*bbox, ctx.ref_gray.shape, pad=4)
    ref_crop = crop_clamped(ctx.ref_gray, x, y, w, h)
    test_crop = crop_clamped(ctx.test_aligned, x, y, w, h)
    scale = 4.0
    ref_big = cv2.resize(ref_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    test_big = cv2.resize(test_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    diff = cv2.absdiff(ref_big, test_big)
    mm = 1.0 - local_ncc(ref_big, test_big, 15)
    stats = _diff_stats(diff, mm)
    supports = stats["mean_diff"] >= 12.0 and stats["mean_mismatch"] >= 0.3
    panel = np.hstack([ref_big, test_big])
    return ToolOutcome(
        tool="highres_zoom",
        region_id=region_id,
        summary=(
            f"Reprocessed existing pixels at 4x: mean_diff={stats['mean_diff']}, "
            f"structural_mismatch={stats['mean_mismatch']}."
        ),
        metrics=stats | {"magnification": scale},
        supports_defect=bool(supports) if stats["mean_diff"] > 4 else None,
        evidence_kind="difference_severity",
        honesty="reprocess",
        artifacts={"zoom_ref_test": panel},
        duration_s=time.perf_counter() - t0,
    )


def tool_edge_topology(ctx: ToolContext, region_id: str, bbox: list[int]) -> ToolOutcome:
    """Edge-based structural comparison.

    Measures (a) how much reference edge structure disappears in the test crop
    (material removal: open circuit / mouse-bite / pinhole) and (b) how much new
    edge structure appears (added copper: spur / spurious copper / short).
    """
    t0 = time.perf_counter()
    x, y, w, h = _pad_bbox(*bbox, ctx.ref_gray.shape, pad=4)
    ref_crop = crop_clamped(ctx.ref_gray, x, y, w, h)
    test_crop = crop_clamped(ctx.test_aligned, x, y, w, h)
    e_ref = cv2.Canny(cv2.GaussianBlur(ref_crop, (3, 3), 0), 60, 140) > 0
    e_test = cv2.Canny(cv2.GaussianBlur(test_crop, (3, 3), 0), 60, 140) > 0
    ref_total = int(e_ref.sum()) + 1e-6
    test_total = int(e_test.sum()) + 1e-6
    # edges present in ref but absent nearby in test (dilated overlap)
    e_test_d = cv2.dilate(e_test.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    e_ref_d = cv2.dilate(e_ref.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    missing_frac = float((e_ref & ~e_test_d).sum() / ref_total)
    new_frac = float((e_test & ~e_ref_d).sum() / test_total)
    mean_test = float(test_crop.mean())
    mean_ref = float(ref_crop.mean())
    polarity = "material_removed" if mean_test < mean_ref else "material_added"
    anomalous = missing_frac > 0.25 or new_frac > 0.25
    panel = np.hstack([
        ref_crop, test_crop,
        (e_ref * 255).astype(np.uint8), (e_test * 255).astype(np.uint8),
    ])
    panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
    return ToolOutcome(
        tool="edge_topology",
        region_id=region_id,
        summary=(
            f"{polarity}: {missing_frac:.0%} of reference edges missing, "
            f"{new_frac:.0%} new edges in test."
        ),
        metrics={
            "missing_edge_frac": round(missing_frac, 4),
            "new_edge_frac": round(new_frac, 4),
            "polarity": polarity,
            "mean_ref": round(mean_ref, 1),
            "mean_test": round(mean_test, 1),
        },
        supports_defect=bool(anomalous),
        evidence_kind="edge_topology",
        honesty="reprocess",
        artifacts={"edges_ref_test_mask": panel},
        duration_s=time.perf_counter() - t0,
    )


def tool_adaptive_threshold(ctx: ToolContext, region_id: str, bbox: list[int]) -> ToolOutcome:
    """Local adaptive-threshold comparison — robust to smooth illumination drift.

    Used to test the 'glare/shadow confound' hypothesis: smooth intensity
    offsets vanish under adaptive thresholding, real geometry changes remain.
    """
    t0 = time.perf_counter()
    x, y, w, h = _pad_bbox(*bbox, ctx.ref_gray.shape, pad=2)
    ref_crop = crop_clamped(ctx.ref_gray, x, y, w, h)
    test_crop = crop_clamped(ctx.test_aligned, x, y, w, h)
    blk = 31 if min(ref_crop.shape[:2]) >= 31 else 15
    b_ref = cv2.adaptiveThreshold(ref_crop, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blk, 10)
    b_test = cv2.adaptiveThreshold(test_crop, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blk, 10)
    changed = float((b_ref != b_test).mean())
    mean_mismatch = float((1.0 - local_ncc(ref_crop, test_crop, 7)).mean())
    residual_after_adapt = changed
    panel = np.hstack([b_ref, b_test])
    supports = changed > 0.12 and mean_mismatch > 0.25
    cleared = changed <= 0.05
    return ToolOutcome(
        tool="adaptive_threshold",
        region_id=region_id,
        summary=(
            f"Adaptive-threshold changed-pixel fraction={changed:.1%}, "
            f"local mismatch={mean_mismatch:.2f}"
            + (" — consistent with pure illumination confound." if cleared else ".")
        ),
        metrics={
            "changed_frac": round(changed, 4),
            "mean_mismatch": round(mean_mismatch, 4),
            "illumination_confound_likely": bool(cleared),
        },
        supports_defect=bool(supports) if not cleared else False,
        evidence_kind="illumination_confound",
        honesty="reprocess",
        artifacts={"adaptive_binary_ref_test": panel},
        duration_s=time.perf_counter() - t0,
    )


def tool_local_realignment(ctx: ToolContext, region_id: str, bbox: list[int]) -> ToolOutcome:
    """Fit surrounding context, then compare the candidate on common pixels.

    ECC returns reference->test, so resampling uses WARP_INVERSE_MAP. Both
    residuals are measured in 0..255 units on the SAME valid core pixels.
    A failed/unobservable fit is inconclusive, never evidence for clearing.
    """
    t0 = time.perf_counter()
    x, y, w, h = _pad_bbox(*bbox, ctx.ref_gray.shape, pad=24)
    ref_crop = crop_clamped(ctx.ref_gray, x, y, w, h).astype(np.float32)
    test_crop = crop_clamped(ctx.test_aligned, x, y, w, h).astype(np.float32)
    valid = (crop_clamped(ctx.valid_mask, x, y, w, h) > 0
             if ctx.valid_mask is not None else np.ones((h, w), dtype=bool))
    core = np.zeros((h, w), np.uint8)
    bx, by, bw, bh = bbox
    core[max(0, by-y):min(h, by+bh-y), max(0, bx-x):min(w, bx+bw-x)] = 1
    # Estimate motion from the surroundings, excluding the suspected change
    # and a halo for ECC's smoothing kernel. Do not fit a defect away.
    fit_mask = valid & ~cv2.dilate(core, np.ones((7, 7), np.uint8)).astype(bool)
    before = after = reduction = cc = 0.0
    common_fraction = 0.0
    max_displacement = 0.0
    residual_component = 0
    reliable = False
    reason = "insufficient observed or textured context"
    enough_context = int(fit_mask.sum()) >= 64
    if enough_context and min(float(ref_crop[fit_mask].std()), float(test_crop[fit_mask].std())) >= 2:
        try:
            cc, warp = cv2.findTransformECC(
                ref_crop / 255.0, test_crop / 255.0, np.eye(2, 3, dtype=np.float32),
                cv2.MOTION_AFFINE, ECC_LOCAL_TERM, (fit_mask.astype(np.uint8) * 255), 5,
            )
            if not np.isfinite(warp).all() or not np.isfinite(cc):
                raise ValueError("non-finite local transform")
            corners = np.float32([[[0, 0], [w-1, 0], [0, h-1], [w-1, h-1]]])
            max_displacement = float(np.linalg.norm(cv2.transform(corners, warp) - corners, axis=2).max())
            determinant = float(np.linalg.det(warp[:, :2]))
            reason = "unreliable or excessive local transform"
            if (np.isfinite(warp).all() and np.isfinite(cc) and cc >= 0.7
                    and 0.9 <= determinant <= 1.1 and max_displacement <= 6.0):
                realigned = cv2.warpAffine(test_crop, warp, (w, h),
                                          flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
                warped_support = cv2.warpAffine(valid.astype(np.float32), warp, (w, h),
                                               flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
                common = valid & (warped_support >= 0.999) & core.astype(bool)
                common_fraction = float(common.sum() / max(int(core.sum()), 1))
                reason = "insufficient common observed candidate pixels"
                if common.sum() >= 8 and common_fraction >= 0.9:
                    before = float(cv2.absdiff(ref_crop, test_crop)[common].mean())
                    residual = cv2.absdiff(ref_crop, realigned)
                    after = float(residual[common].mean())
                    reduction = float(np.clip(1.0 - (after + 1e-6) / (before + 1e-6), -1, 1))
                    # A large average improvement can still leave a tiny real
                    # defect. Retain any coherent residual instead of clearing.
                    remaining = ((residual >= 12) & common).astype(np.uint8)
                    _, _, stats, _ = cv2.connectedComponentsWithStats(remaining, connectivity=8)
                    residual_component = int(stats[1:, cv2.CC_STAT_AREA].max()) if len(stats) > 1 else 0
                    reliable = True
                    reason = "common observed support and bounded context alignment"
        except (cv2.error, ValueError):
            reason = "local ECC did not converge or produced a non-finite transform"
    metrics = {
        "mean_diff_before": round(before, 2),
        "mean_diff_after": round(after, 2),
        "reduction_ratio": round(reduction, 4),
        "ecc_correlation": round(float(cc), 4) if np.isfinite(cc) else 0.0,
        "comparison_reliable": reliable,
        "common_valid_fraction": round(common_fraction, 4),
        "max_displacement_px": round(max_displacement, 3) if np.isfinite(max_displacement) else 0.0,
        "residual_component_area_px": residual_component,
        "measurement_version": "local_ecc_v2",
        "intensity_scale": "0..255",
        "comparison_reason": reason,
    }
    supports = None
    summary = ""
    if not reliable:
        summary = f"Local alignment inconclusive: {reason}; retain review."
    elif reduction > 0.7 and after <= 4.0 and residual_component < 3:
        supports = False
        summary = f"Local ECC alignment removed {reduction:.0%} of the difference — registration artifact."
    elif reduction < 0.25 and after > 4.0:
        supports = True
        summary = f"Local alignment leaves {after:.1f} mean diff ({reduction:.0%} change) — difference is real geometry, not alignment."
    else:
        summary = f"Local alignment reduces difference by {reduction:.0%} — inconclusive."
    return ToolOutcome(
        tool="local_realignment",
        region_id=region_id,
        summary=summary,
        metrics=metrics,
        supports_defect=supports,
        evidence_kind="local_realignment",
        honesty="reprocess",
        artifacts={},
        duration_s=time.perf_counter() - t0,
    )


def tool_alternate_view(ctx: ToolContext, region_id: str, bbox: list[int]) -> ToolOutcome:
    """Re-check the region in an independent captured view of the same board.

    Genuinely new optical evidence (a second capture), not reprocessing. When no
    secondary view exists the outcome is explicitly 'additional_capture_required'.
    """
    t0 = time.perf_counter()
    if ctx.secondary_view_gray is None or ctx.secondary_aligned is None:
        return ToolOutcome(
            tool="alternate_view",
            region_id=region_id,
            summary="No secondary view available for this inspection — additional capture required.",
            metrics={"secondary_view_available": False},
            supports_defect=None,
            evidence_kind="independent_view",
            honesty="request",
            duration_s=time.perf_counter() - t0,
        )
    x, y, w, h = _pad_bbox(*bbox, ctx.secondary_aligned.shape, pad=2)
    ref_crop = crop_clamped(ctx.ref_gray, x, y, w, h)
    v2_crop = crop_clamped(ctx.secondary_aligned, x, y, w, h)
    diff = cv2.absdiff(ref_crop, v2_crop)
    mm = 1.0 - local_ncc(ref_crop, v2_crop, 15)
    stats = _diff_stats(diff, mm)
    # quality gate: if this view is misaligned locally the comparison is junk
    gate_ok = stats["mean_mismatch"] > 0.2 or stats["mean_diff"] > 8
    # persistence gate sits above noise: an anomaly must clearly reproduce in
    # the independent capture (tuned so clean-board noise blips do not)
    persists = stats["mean_diff"] >= 14.0 and stats["mean_mismatch"] >= 0.35
    supports = bool(persists) if gate_ok else None
    # wide view for the artifact panel
    wx, wy, ww, wh = _pad_bbox(*bbox, ctx.secondary_aligned.shape, pad=8)
    panel = np.hstack([
        crop_clamped(ctx.ref_gray, wx, wy, ww, wh),
        crop_clamped(ctx.secondary_aligned, wx, wy, ww, wh),
        cv2.absdiff(crop_clamped(ctx.ref_gray, wx, wy, ww, wh), crop_clamped(ctx.secondary_aligned, wx, wy, ww, wh)),
    ])
    return ToolOutcome(
        tool="alternate_view",
        region_id=region_id,
        summary=(
            f"Independent view {'shows' if persists else 'does not show'} the anomaly "
            f"(mean_diff={stats['mean_diff']}, mismatch={stats['mean_mismatch']})."
        ),
        metrics=stats | {"secondary_view_available": True, "comparison_reliable": gate_ok},
        supports_defect=supports,
        evidence_kind="independent_view",
        honesty="alternate_view",
        artifacts={"independent_view_ref_test_diff": panel},
        duration_s=time.perf_counter() - t0,
    )


def tool_request_capture(ctx: ToolContext, region_id: str, bbox: list[int]) -> ToolOutcome:
    """Open an operator capture request for genuinely new visual evidence."""
    return ToolOutcome(
        tool="request_capture",
        region_id=region_id,
        summary="Operator capture requested for this region — inspection paused pending new evidence.",
        metrics={"requested": True, "bbox": bbox},
        supports_defect=None,
        evidence_kind="independent_view",
        honesty="request",
    )


TOOL_FUNCTIONS = {
    "highres_zoom": tool_highres_zoom,
    "edge_topology": tool_edge_topology,
    "adaptive_threshold": tool_adaptive_threshold,
    "local_realignment": tool_local_realignment,
    "alternate_view": tool_alternate_view,
    "request_capture": tool_request_capture,
}
