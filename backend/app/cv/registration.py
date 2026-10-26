"""Stage 3 — image registration (test -> reference alignment).

Strategy ladder (each attempt recorded; first success that meets the quality
gate wins, otherwise the best attempt is returned with its measured quality):

1. SIFT + FLANN/BF knn + Lowe ratio + RANSAC partial-affine   (most accurate)
2. ORB (dense nfeatures) + BF knn + ratio + RANSAC            (fast fallback)
3. ECC refinement from identity on downscaled pair            (ill-featured or
   mostly-uniform boards where keypoints are sparse)

ECC is additionally used as a *refinement* step after keypoint registration.

Quality model (documented heuristics, not probabilities):
  good     : inliers >= good_inliers AND inlier_ratio >= good_inlier_ratio
             AND mean residual <= good_residual_px
  marginal : inliers >= marginal_inliers AND mean residual <= marginal_residual_px
  poor     : a transform was estimated but gates failed
  failed   : no transform could be estimated

The agent refuses to report confident defects when quality is poor/failed and
instead triggers recovery (next strategy, local re-registration) or the
NOT_EVALUABLE path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from ..config import settings
from .preprocess import PreprocessParams, preprocess

MOTION_AFFINE = cv2.MOTION_AFFINE
ECC_TERM = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 120, 1e-7)


@dataclass
class RegistrationResult:
    warp: np.ndarray | None                 # 2x3 float32, maps test -> reference
    warped_test: np.ndarray | None          # warped grayscale test image
    valid_mask: np.ndarray | None           # uint8 255 where warped pixels exist
    metrics: dict = field(default_factory=dict)

    @property
    def quality(self) -> str:
        return str(self.metrics.get("quality", "failed"))

    @property
    def ok(self) -> bool:
        return self.warp is not None and self.quality in ("good", "marginal")


def _coverage_score(points: np.ndarray, shape: tuple[int, int]) -> float:
    """Fraction of a 4x4 grid of cells over the frame containing >=1 inlier.

    Measures whether matches span the board (global alignment) instead of
    locking onto one repetitive pad cluster.
    """
    h, w = shape
    if len(points) == 0:
        return 0.0
    gx = np.clip((points[:, 0] / max(w, 1) * 4).astype(int), 0, 3)
    gy = np.clip((points[:, 1] / max(h, 1) * 4).astype(int), 0, 3)
    cells = set(zip(gx.tolist(), gy.tolist()))
    return len(cells) / 16.0


def _classify(inliers: int, ratio: float, residual: float, coverage: float) -> tuple[str, str | None]:
    s = settings
    if (
        inliers >= s.good_inliers
        and ratio >= s.good_inlier_ratio
        and residual <= s.good_residual_px
        and coverage >= 0.5
    ):
        return "good", None
    if inliers >= s.marginal_inliers and residual <= s.marginal_residual_px and coverage >= 0.35:
        return "marginal", None
    return "poor", (
        "quality gates failed (inliers=%d ratio=%.2f residual=%.2f coverage=%.2f)"
        % (inliers, ratio, residual, coverage)
    )


def _match_mutual(kp_t, des_t, kp_r, des_r, norm, ratio=0.75):
    """Mutual + ratio-test matching.

    On repetitive PCB textures one-directional matching admits many wrong
    correspondences that RANSAC can still fit into a self-consistent but
    wrong near-identity warp. Requiring the match to hold in both directions
    removes most of those.
    """
    matcher = cv2.BFMatcher(norm)
    knn_tr = matcher.knnMatch(des_t, des_r, k=2)
    knn_rt = matcher.knnMatch(des_r, des_t, k=2)
    best_rt = {}
    for pair in knn_rt:
        if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance:
            best_rt[pair[0].queryIdx] = pair[0].trainIdx
    good = []
    for pair in knn_tr:
        if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance:
            m = pair[0]
            if best_rt.get(m.trainIdx) == m.queryIdx:
                good.append(m)
    return good


def _photometric_score(
    ref_small: np.ndarray, test_small: np.ndarray, warp_small: np.ndarray
) -> float:
    """Masked zero-mean normalized correlation between the reference and the
    warped test, on a downscaled pair. The globally correct alignment
    maximizes photometric agreement; self-similar false hypotheses (repetitive
    trace grids) mismatch silk, fiducials and pads, so they score lower."""
    h, w = ref_small.shape[:2]
    warped = cv2.warpAffine(test_small, warp_small, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    ones = np.ones_like(test_small) * 255
    mask = cv2.warpAffine(ones, warp_small, (w, h), flags=cv2.INTER_NEAREST, borderValue=0) > 0
    if mask.sum() < 500:
        return -1.0
    a = ref_small[mask].astype(np.float32)
    b = warped[mask].astype(np.float32)
    a -= a.mean()
    b -= b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum())) + 1e-6
    return float((a * b).sum() / denom)


def _keypoint_attempt(
    ref: np.ndarray, test: np.ndarray, detector_name: str
) -> RegistrationResult:
    h, w = ref.shape[:2]
    if detector_name == "SIFT":
        det = cv2.SIFT_create(nfeatures=6000)
        norm = cv2.NORM_L2
    else:
        det = cv2.ORB_create(nfeatures=8000, patchSize=31)
        norm = cv2.NORM_HAMMING
    kp_r, des_r = det.detectAndCompute(ref, None)
    kp_t, des_t = det.detectAndCompute(test, None)
    base = {
        "detector": detector_name,
        "keypoints_reference": len(kp_r),
        "keypoints_test": len(kp_t),
        "attempts": [detector_name],
    }
    if des_r is None or des_t is None or len(kp_r) < 8 or len(kp_t) < 8:
        base.update(quality="failed", failure_reason=f"insufficient keypoints ({len(kp_r)}/{len(kp_t)})")
        return RegistrationResult(None, None, None, base)

    good = _match_mutual(kp_t, des_t, kp_r, des_r, norm)
    base["good_matches"] = len(good)
    if len(good) < 8:
        base.update(quality="failed", failure_reason=f"only {len(good)} mutual ratio-test matches")
        return RegistrationResult(None, None, None, base)

    src = np.float32([kp_t[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_r[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    # Multiple RANSAC hypotheses, verified photometrically. Inlier count alone
    # is misleading on repetitive layouts: a wrong warp can map trace rows onto
    # trace rows (period pitch) and gather huge false consensus.
    ref_small = cv2.resize(ref, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    test_small = cv2.resize(test, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    candidates_warp: list[tuple[float, np.ndarray, int, float]] = []
    for _ in range(4):
        cand_warp, inl = cv2.estimateAffinePartial2D(
            src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0, maxIters=5000, confidence=0.999
        )
        if cand_warp is None or inl is None or int(inl.sum()) < 6:
            continue
        inl_mask = inl.ravel().astype(bool)
        count = int(inl_mask.sum())
        in_src = src[inl_mask].reshape(-1, 2)
        in_dst = dst[inl_mask].reshape(-1, 2)
        pred = cv2.transform(in_src.reshape(-1, 1, 2), cand_warp).reshape(-1, 2)
        res = float(np.mean(np.linalg.norm(pred - in_dst, axis=1)))
        score = _photometric_score(
            ref_small, test_small,
            np.array([[cand_warp[0, 0], cand_warp[0, 1], cand_warp[0, 2] / 2.0],
                      [cand_warp[1, 0], cand_warp[1, 1], cand_warp[1, 2] / 2.0]], np.float64),
        )
        candidates_warp.append((score, cand_warp, count, res))

    if not candidates_warp:
        base.update(quality="failed", failure_reason="RANSAC could not estimate a transform")
        return RegistrationResult(None, None, None, base)

    candidates_warp.sort(key=lambda t: -t[0])
    best_score, warp, inlier_count, residual = candidates_warp[0]
    inlier_ratio = inlier_count / len(good)
    # inlier source points for the coverage metric, under the chosen warp
    close = np.linalg.norm(
        cv2.transform(src, warp).reshape(-1, 2) - dst.reshape(-1, 2), axis=1
    )
    in_src = src[close <= 3.0].reshape(-1, 2)
    if len(in_src) < 6:
        in_src = src.reshape(-1, 2)
    coverage = _coverage_score(in_src, (h, w))
    quality, reason = _classify(inlier_count, inlier_ratio, residual, coverage)
    metrics = dict(base)
    metrics.update(
        inliers=inlier_count,
        inlier_ratio=round(inlier_ratio, 4),
        mean_residual_px=round(residual, 3),
        coverage_score=round(coverage, 3),
        photometric_score=round(best_score, 4),
        quality=quality,
        failure_reason=reason,
    )
    if quality in ("good", "marginal") and best_score > 0.3:
        warped, mask = _warp_to_reference(test, warp.astype(np.float32), (w, h))
        return RegistrationResult(warp.astype(np.float32), warped, mask, metrics)
    metrics["quality"] = "poor"
    metrics["failure_reason"] = (
        metrics.get("failure_reason")
        or f"photometric verification too low ({best_score:.2f})"
    )
    return RegistrationResult(None, None, None, metrics)


def _warp_to_reference(
    test: np.ndarray, warp: np.ndarray, size: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    warped = cv2.warpAffine(
        test, warp, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )
    ones = np.ones(test.shape[:2], np.uint8) * 255
    mask = cv2.warpAffine(ones, warp, size, flags=cv2.INTER_NEAREST, borderValue=0)
    return warped, mask


def _invert_ecc_warp(warp: np.ndarray) -> np.ndarray:
    """Cross the ECC reference->test boundary; public warps map test->reference.

    Reject non-finite, singular and reflected updates rather than passing an
    unusable transform to downstream pixel/evidence operations.
    """
    matrix = np.asarray(warp, dtype=np.float32).reshape(2, 3)
    if not np.isfinite(matrix).all() or np.linalg.det(matrix[:, :2]) <= 1e-6:
        raise ValueError("invalid ECC affine transform")
    return cv2.invertAffineTransform(matrix).astype(np.float32)


def _ecc_attempt(ref: np.ndarray, test: np.ndarray, init: np.ndarray | None) -> RegistrationResult:
    """ECC alignment, coarse-to-fine; accepts/returns a forward test->ref warp."""
    h, w = ref.shape[:2]
    attempts_info: list[str] = ["ECC"]
    try:
        # ECC optimizes the opposite mapping, including its initializer.
        warp = np.eye(2, 3, dtype=np.float32) if init is None else _invert_ecc_warp(init)
    except ValueError as exc:
        return RegistrationResult(None, None, None, {
            "detector": "ECC", "attempts": attempts_info, "quality": "failed",
            "failure_reason": str(exc),
        })
    scale = 1.0
    for scale in (0.5, 1.0):  # coarse first for large displacements
        small_ref = cv2.resize(ref, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        small_test = cv2.resize(test, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        small_warp = warp.copy()
        small_warp[:, 2] *= scale
        try:
            cc, small_warp = cv2.findTransformECC(
                small_ref.astype(np.float32) / 255.0,
                small_test.astype(np.float32) / 255.0,
                np.ascontiguousarray(small_warp, dtype=np.float32),
                MOTION_AFFINE,
                ECC_TERM,
                None,
                5,
            )
        except cv2.error as exc:
            return RegistrationResult(
                None, None, None,
                {"detector": "ECC", "attempts": attempts_info, "quality": "failed",
                 "failure_reason": f"ECC error at scale {scale}: {exc}"},
            )
        warp = small_warp.copy()
        warp[:, 2] /= scale
    # Convert the full-resolution ECC result back to the public convention.
    try:
        warp = _invert_ecc_warp(warp)
    except ValueError as exc:
        return RegistrationResult(None, None, None, {
            "detector": "ECC", "attempts": attempts_info, "quality": "failed",
            "failure_reason": str(exc),
        })
    if not np.isfinite(cc) or cc < 0.65:
        # Two different boards can still reach moderate ECC correlation because
        # of shared layout style; require strong correlation before trusting a
        # keypoint-less alignment.
        return RegistrationResult(
            None, None, None,
            {"detector": "ECC", "attempts": attempts_info, "quality": "failed",
             "failure_reason": f"ECC correlation too low ({cc:.3f})"},
        )
    warped, mask = _warp_to_reference(test, warp.astype(np.float32), (w, h))
    metrics = {
        "detector": "ECC",
        "attempts": attempts_info,
        "ecc_correlation": round(float(cc), 4),
        "warp": warp.round(5).tolist(),
        "quality": "marginal",
        "failure_reason": None,
    }
    return RegistrationResult(warp.astype(np.float32), warped, mask, metrics)


def _ecc_refine(ref: np.ndarray, test: np.ndarray, warp: np.ndarray) -> tuple[np.ndarray, float]:
    """Refine a keypoint-estimated warp with ECC; fall back to input on error."""
    try:
        cc, refined = cv2.findTransformECC(
            ref.astype(np.float32) / 255.0,
            test.astype(np.float32) / 255.0,
            np.ascontiguousarray(_invert_ecc_warp(warp)),
            MOTION_AFFINE,
            ECC_TERM,
            None,
            5,
        )
        if np.isfinite(cc) and cc > 0.1:
            return _invert_ecc_warp(refined), float(cc)
    except (cv2.error, ValueError):
        pass
    return warp.astype(np.float32), 0.0


def register(
    ref_gray: np.ndarray,
    test_gray: np.ndarray,
    params: PreprocessParams | None = None,
) -> RegistrationResult:
    """Full registration ladder. `ref_gray`/`test_gray` are uint8 grayscale."""
    p = params or PreprocessParams()
    ref = preprocess(ref_gray, p, for_registration=True)
    test = preprocess(test_gray, p, for_registration=True)

    attempts: list[RegistrationResult] = []
    trace: list[str] = []
    for name in ("SIFT", "ORB"):
        res = _keypoint_attempt(ref, test, name)
        attempts.append(res)
        trace.extend(res.metrics.get("attempts", [name]))
        if res.ok:
            refined, ecc_cc = _ecc_refine(ref, test, res.warp)
            if ecc_cc > 0:
                trace.append("ECC-refine")
                h, w = ref.shape[:2]
                # ECC is only locally convergent: on near-periodic layouts it
                # can slide to a trace-row-aligned local optimum. Accept the
                # refinement only if photometric agreement does not degrade.
                small_ref = cv2.resize(ref, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
                small_test = cv2.resize(test, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
                half = np.array(
                    [[refined[0, 0], refined[0, 1], refined[0, 2] / 2.0],
                     [refined[1, 0], refined[1, 1], refined[1, 2] / 2.0]], np.float64
                )
                score_refined = _photometric_score(small_ref, small_test, half)
                score_before = res.metrics.get("photometric_score", -1.0)
                if score_refined >= score_before - 0.02:
                    warped, mask = _warp_to_reference(test, refined, (w, h))
                    res.warp = refined
                    res.warped_test = warped
                    res.valid_mask = mask
                    res.metrics["ecc_refine_correlation"] = round(ecc_cc, 4)
                    res.metrics["photometric_score"] = round(score_refined, 4)
                else:
                    res.metrics["ecc_refine_rejected"] = True
            res.metrics["attempts"] = list(trace)
            return res
        if res.metrics.get("quality") == "poor":
            # keep best poor result around in case everything else fails
            best_poor = res
            break
    else:
        best_poor = None

    ecc = _ecc_attempt(ref, test, None)
    attempts.append(ecc)
    trace.extend(ecc.metrics.get("attempts", ["ECC"]))
    if ecc.ok:
        ecc.metrics["attempts"] = list(trace)
        return ecc

    if best_poor is not None:
        best_poor.metrics["attempts"] = list(trace) + [ecc.metrics.get("detector", "ECC")]
        return best_poor

    failed = RegistrationResult(
        None, None, None,
        {
            "detector": "SIFT",
            "keypoints_reference": 0,
            "keypoints_test": 0,
            "good_matches": 0,
            "inliers": 0,
            "inlier_ratio": 0.0,
            "mean_residual_px": 0.0,
            "coverage_score": 0.0,
            "warp_matrix": [],
            "attempts": list(trace),
            "quality": "failed",
            "failure_reason": "all registration strategies failed",
        },
    )
    return failed
