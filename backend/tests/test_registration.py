"""Registration tests: warp recovery, quality gates, failure refusal."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.cv.imaging import load_bgr, to_grayscale
from app.cv.preprocess import PreprocessParams
from app.cv.registration import register


def _gray(path):
    return to_grayscale(load_bgr(path))


def test_exact_shift_recovered(scenario_paths):
    ref = _gray(scenario_paths["scenario_01_clear_defects"] / "reference.png")
    # shift the reference by a known amount -> registration should undo it
    M = np.float32([[1, 0, 6], [0, 1, 4]])
    shifted = cv2.warpAffine(ref, M, (ref.shape[1], ref.shape[0]))
    res = register(ref, shifted, PreprocessParams())
    assert res.ok
    assert res.metrics["quality"] == "good"
    dx = res.warp[0, 2] - (-6.0)
    dy = res.warp[1, 2] - (-4.0)
    assert abs(dx) < 0.75 and abs(dy) < 0.75, f"warp off: {res.warp}"


def test_mismatched_boards_refuse_alignment(scenario_paths):
    """Scenario 4 is a different board: the gates must not bless a bogus warp."""
    s4 = scenario_paths["scenario_04_registration_failure"]
    res = register(_gray(s4 / "reference.png"), _gray(s4 / "test.png"), PreprocessParams())
    assert not res.ok
    assert res.quality in ("poor", "failed")
    assert res.metrics.get("failure_reason")


def test_quality_metrics_present(scenario_paths):
    s1 = scenario_paths["scenario_01_clear_defects"]
    res = register(_gray(s1 / "reference.png"), _gray(s1 / "test.png"), PreprocessParams())
    for key in ("inliers", "inlier_ratio", "mean_residual_px", "coverage_score", "attempts", "detector"):
        assert key in res.metrics, key
    assert res.metrics["inliers"] >= 30
    assert 0.35 <= res.metrics["inlier_ratio"] <= 1.0
    assert res.metrics["coverage_score"] >= 0.5
