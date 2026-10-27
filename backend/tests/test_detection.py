"""Detection tests: ground-truth IoU matching, clean-board restraint."""

from __future__ import annotations

import json

from app.cv.detection import DetectionParams, detect_candidates
from app.cv.imaging import load_bgr, to_grayscale
from app.cv.preprocess import PreprocessParams, preprocess
from app.cv.registration import register


def _detect(scenario_dir):
    ref = to_grayscale(load_bgr(scenario_dir / "reference.png"))
    test = to_grayscale(load_bgr(scenario_dir / "test.png"))
    p = PreprocessParams()
    reg = register(ref, test, p)
    if not reg.ok:
        return reg, None
    det = detect_candidates(
        preprocess(ref, p, for_registration=False), reg.warped_test, reg.valid_mask, DetectionParams()
    )
    return reg, det


def _iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / (aw * ah + bw * bh - inter)


def test_all_gross_defects_found_with_zero_fp(scenario_paths):
    reg, det = _detect(scenario_paths["scenario_01_clear_defects"])
    assert reg.ok
    gt = json.loads((scenario_paths["scenario_01_clear_defects"] / "annotations.json").read_text())
    assert det is not None and len(det.candidates) >= 1
    matched = 0
    for g in gt:
        best = max(_iou(g["bbox"], c["bbox"]) for c in det.candidates)
        if best > 0.15:
            matched += 1
    assert matched == len(gt), "every injected defect must be detected"
    assert len(det.candidates) == len(gt), "no false positives on the clean background"


def test_clean_board_produces_no_candidates(scenario_paths):
    reg, det = _detect(scenario_paths["scenario_02_clean_board"])
    assert reg.ok
    assert det is not None
    assert det.candidates == [], "clean board must not manufacture defects"


def test_glare_does_not_spawn_reported_false_candidates(scenario_paths):
    """The glare blob may create transient candidates, but the pinhole must be
    among them and glare artifacts must carry the illumination flag or low
    evidence so the agent can clear them cheaply."""
    reg, det = _detect(scenario_paths["scenario_03_ambiguous_glare"])
    assert reg.ok
    gt = json.loads((scenario_paths["scenario_03_ambiguous_glare"] / "annotations.json").read_text())
    assert det is not None and det.candidates
    best = max(_iou(gt[0]["bbox"], c["bbox"]) for c in det.candidates)
    assert best > 0.15, "the real pinhole must survive detection under glare"


def test_candidate_schema_complete(scenario_paths):
    _, det = _detect(scenario_paths["scenario_01_clear_defects"])
    c = det.candidates[0]
    for key in ("bbox", "area_px", "centroid", "difference_score", "structural_mismatch_score",
                "evidence_quality_score", "edge_delta", "touches_invalid_warp_region",
                "illumination_suspect"):
        assert key in c
    assert 0 <= c["difference_score"] <= 1.5
    assert 0 <= c["structural_mismatch_score"] <= 1.0


def test_clipped_glare_does_not_become_a_structural_candidate():
    import numpy as np
    checker = (np.indices((256, 256)).sum(axis=0) // 8 % 2 * 80 + 80).astype(np.uint8)
    clipped = checker.copy()
    clipped[100:120, 100:120] = 255
    result = detect_candidates(checker, clipped, np.full_like(checker, 255))
    assert not any(_iou([100, 100, 20, 20], c["bbox"]) > .15 for c in result.candidates)
