"""Region tool + verification rule tests."""

from __future__ import annotations

import asyncio

import numpy as np

from app.cv import region_tools as rt
from app.cv import verification as ver
from app.cv.detection import detect_candidates
from app.cv.imaging import load_bgr, to_grayscale
from app.cv.preprocess import PreprocessParams, preprocess
from app.cv.registration import register


def _ctx(scenario_dir):
    ref = to_grayscale(load_bgr(scenario_dir / "reference.png"))
    test = to_grayscale(load_bgr(scenario_dir / "test.png"))
    p = PreprocessParams()
    reg = register(ref, test, p)
    ref_det = preprocess(ref, p, for_registration=False)
    diff = np.abs(ref_det.astype(np.float32) - reg.warped_test.astype(np.float32))
    from app.cv.detection import local_ncc

    return rt.ToolContext(
        ref_gray=ref_det, test_aligned=reg.warped_test, test_original=reg.warped_test,
        valid_mask=reg.valid_mask, diff_map=diff, mismatch_map=1.0 - local_ncc(ref_det, reg.warped_test),
    ), reg


def _first_candidate(scenario_dir):
    ref = to_grayscale(load_bgr(scenario_dir / "reference.png"))
    test = to_grayscale(load_bgr(scenario_dir / "test.png"))
    p = PreprocessParams()
    reg = register(ref, test, p)
    det = detect_candidates(preprocess(ref, p, for_registration=False), reg.warped_test, reg.valid_mask)
    return det.candidates[0]


def test_alternate_view_without_view_requires_capture(scenario_paths):
    ctx, _ = _ctx(scenario_paths["scenario_05_no_second_view"])
    cand = _first_candidate(scenario_paths["scenario_05_no_second_view"])
    out = rt.tool_alternate_view(ctx, "R01", cand["bbox"])
    assert out.supports_defect is None
    assert out.metrics["secondary_view_available"] is False


def test_alternate_view_with_view_confirms_persists(scenario_paths):
    from app.cv.detection import local_ncc

    sd = scenario_paths["scenario_01_clear_defects"]
    ref = to_grayscale(load_bgr(sd / "reference.png"))
    test = to_grayscale(load_bgr(sd / "test.png"))
    v2 = to_grayscale(load_bgr(sd / "view2.png"))
    p = PreprocessParams()
    reg = register(ref, test, p)
    ref_det = preprocess(ref, p, for_registration=False)
    v2_det = preprocess(v2, p, for_registration=False)
    v2reg = register(ref_det, v2_det, p)
    assert v2reg.ok
    ctx = rt.ToolContext(
        ref_gray=ref_det, test_aligned=reg.warped_test, test_original=reg.warped_test,
        valid_mask=reg.valid_mask,
        diff_map=np.abs(ref_det.astype(np.float32) - reg.warped_test.astype(np.float32)),
        mismatch_map=1.0 - local_ncc(ref_det, reg.warped_test),
        secondary_view_gray=v2_det, secondary_aligned=v2reg.warped_test,
        secondary_valid_mask=v2reg.valid_mask,
    )
    det = detect_candidates(ref_det, reg.warped_test, reg.valid_mask)
    out = rt.tool_alternate_view(ctx, "R01", det.candidates[0]["bbox"])
    assert out.honesty == "alternate_view"
    assert out.metrics["secondary_view_available"] is True


def test_edge_topology_polarity_material_removed(scenario_paths):
    ctx, _ = _ctx(scenario_paths["scenario_01_clear_defects"])
    cand = _first_candidate(scenario_paths["scenario_01_clear_defects"])
    out = rt.tool_edge_topology(ctx, "R01", cand["bbox"])
    assert out.metrics["polarity"] in ("material_removed", "material_added")
    assert isinstance(out.supports_defect, bool)


def test_verification_rule_table():
    base = {
        "difference_score": 0.3, "structural_mismatch_score": 0.5,
        "evidence_quality_score": 0.7, "area_px": 100,
        "illumination_suspect": False, "touches_invalid_warp_region": False,
        "edge_delta": -0.5,
    }
    ev_view_yes = [{"evidence_kind": "independent_view", "source_tool": "alternate_view",
                    "supports_defect": True, "metrics": {}}]
    verdict, label, _, _ = ver.verify_candidate(base, ev_view_yes, "good")
    assert verdict == "CONFIRMED_DEFECT" and label

    ev_view_no = [{"evidence_kind": "independent_view", "source_tool": "alternate_view",
                   "supports_defect": False, "metrics": {}}]
    verdict, _, _, notes = ver.verify_candidate(base, ev_view_no, "good")
    assert verdict == "NEEDS_REVIEW"  # strong baseline vs refute = honest conflict

    weak = dict(base, difference_score=0.05, structural_mismatch_score=0.1)
    verdict, _, _, _ = ver.verify_candidate(weak, ev_view_no, "good")
    assert verdict == "CLEARED"

    ev_realign_cleared = [{"evidence_kind": "local_realignment", "source_tool": "local_realignment",
                           "supports_defect": False,
                           "metrics": {"reduction_ratio": 0.9, "comparison_reliable": True}}]
    verdict, _, basis, _ = ver.verify_candidate(base, ev_realign_cleared, "good")
    assert verdict == "CLEARED" and "artifact" in basis

    verdict, _, _, _ = ver.verify_candidate(base, [], "poor")
    assert verdict == "NOT_EVALUABLE"

    illum = dict(base, illumination_suspect=True, difference_score=0.2,
                 structural_mismatch_score=0.1)
    ev_adapt_clear = [{"evidence_kind": "illumination_confound", "source_tool": "adaptive_threshold",
                       "supports_defect": False, "metrics": {"illumination_confound_likely": True}}]
    verdict, _, basis, _ = ver.verify_candidate(illum, ev_adapt_clear, "good")
    assert verdict == "CLEARED" and "illumination" in basis


def test_classification_hedges():
    cand = {"area_px": 300, "difference_score": 0.3, "edge_delta": -0.5}
    label, basis = ver._classify(cand, [])
    assert label == "open_circuit_suspected"
    cand2 = {"area_px": 50, "difference_score": 0.05, "edge_delta": 0.0}
    label, _ = ver._classify(cand2, [])
    assert label == "unclassified_surface_anomaly"
