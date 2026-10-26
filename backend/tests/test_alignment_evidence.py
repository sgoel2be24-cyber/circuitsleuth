"""Known-motion and evidence-conflict regressions, independent of PCB templates."""

import cv2
import numpy as np
import pytest

from app.cv import registration as reg
from app.cv import region_tools as rt
from app.cv.verification import verify_candidate


def texture():
    rng = np.random.default_rng(8)
    image = cv2.GaussianBlur(rng.integers(15, 240, (240, 320), dtype=np.uint8), (7, 7), 0)
    cv2.putText(image, 'PCB 26', (35, 125), cv2.FONT_HERSHEY_SIMPLEX, 1.5, 230, 3)
    return image


def context(ref, test, valid=None):
    return rt.ToolContext(ref, test, test, valid, cv2.absdiff(ref, test), np.zeros_like(ref, dtype=np.float32))


def candidate():
    return dict(difference_score=0.3, structural_mismatch_score=0.7,
                evidence_quality_score=0.9, area_px=100)


def evidence(kind, supports, reliable=True):
    return dict(evidence_kind=kind, source_tool=kind, supports_defect=supports,
                metrics=dict(comparison_reliable=reliable, reduction_ratio=0.9))


@pytest.mark.parametrize('init', [None, np.float32([[1, 0, -2.5], [0, 1, 1.5]])])
def test_ecc_pyramid_returns_forward_test_to_reference(init):
    ref = texture()
    shifted = cv2.warpAffine(ref, np.float32([[1, 0, 3], [0, 1, -2]]), (320, 240))
    result = reg._ecc_attempt(ref, shifted, init)
    assert result.ok
    np.testing.assert_allclose(result.warp[:, 2], [-3, 2], atol=0.6)
    interior = np.s_[20:-20, 20:-20]
    error = np.abs(ref[interior].astype(float) - result.warped_test[interior]).mean()
    assert error < 3.0


def test_ecc_refinement_inverts_initializer_and_result():
    ref = texture()
    shifted = cv2.warpAffine(ref, np.float32([[1, 0, 3], [0, 1, -2]]), (320, 240))
    refined, correlation = reg._ecc_refine(ref, shifted, np.float32([[1, 0, -2.5], [0, 1, 1.5]]))
    assert correlation > 0.9
    np.testing.assert_allclose(refined[:, 2], [-3, 2], atol=0.6)


@pytest.mark.parametrize('bad_warp', [
    np.float32([[0, 0, 0], [0, 0, 0]]),
    np.float32([[-1, 0, 0], [0, 1, 0]]),
    np.float32([[1, 0, np.nan], [0, 1, 0]]),
])
def test_invalid_ecc_output_never_replaces_input(monkeypatch, bad_warp):
    monkeypatch.setattr(cv2, 'findTransformECC', lambda *a: (0.99, bad_warp.copy()))
    initial = np.float32([[1, 0, -3], [0, 1, 2]])
    refined, correlation = reg._ecc_refine(texture(), texture(), initial)
    np.testing.assert_array_equal(refined, initial)
    assert correlation == 0
    assert not reg._ecc_attempt(texture(), texture(), None).ok


def test_local_defect_is_not_erased_by_mixed_units():
    ref = texture()
    test = ref.copy()
    cv2.circle(test, (150, 120), 9, 20, -1)
    outcome = rt.tool_local_realignment(context(ref, test), 'R01', [138, 108, 24, 24])
    assert outcome.supports_defect is not False
    assert outcome.metrics['mean_diff_after'] > 1.0 or not outcome.metrics['comparison_reliable']
    assert outcome.metrics['measurement_version'] == 'local_ecc_v2'


def test_local_translation_can_clear_with_common_support():
    ref = texture()
    shifted = cv2.warpAffine(ref, np.float32([[1, 0, 2], [0, 1, -1]]), (320, 240))
    outcome = rt.tool_local_realignment(context(ref, shifted), 'R01', [100, 80, 90, 70])
    assert outcome.metrics['comparison_reliable'] is True
    assert outcome.metrics['mean_diff_after'] < 2
    assert outcome.metrics['reduction_ratio'] > 0.7
    assert outcome.supports_defect is False


def test_local_translation_with_real_defect_must_not_clear():
    ref = texture()
    defective = ref.copy()
    cv2.circle(defective, (150, 120), 6, 10, -1)
    shifted = cv2.warpAffine(defective, np.float32([[1, 0, 2], [0, 1, -1]]), (320, 240))
    outcome = rt.tool_local_realignment(context(ref, shifted), 'R01', [100, 80, 90, 70])
    assert outcome.supports_defect is not False


def test_local_ecc_failure_is_inconclusive(monkeypatch):
    def fail(*args):
        raise cv2.error('did not converge')
    monkeypatch.setattr(cv2, 'findTransformECC', fail)
    ref = texture()
    outcome = rt.tool_local_realignment(context(ref, ref), 'R01', [100, 80, 40, 40])
    assert outcome.supports_defect is None
    assert outcome.metrics['comparison_reliable'] is False


@pytest.mark.parametrize('mode', ['blank', 'missing_support'])
def test_local_unobservable_regions_are_inconclusive(mode):
    ref = np.full((240, 320), 80, np.uint8) if mode == 'blank' else texture()
    valid = np.zeros_like(ref) if mode == 'missing_support' else None
    outcome = rt.tool_local_realignment(context(ref, ref, valid), 'R01', [100, 80, 40, 40])
    assert outcome.supports_defect is None
    assert outcome.metrics['comparison_reliable'] is False


@pytest.mark.parametrize('local,view', [(False, True), (True, False)])
def test_conflicting_local_and_independent_evidence_requires_review(local, view):
    ev = [evidence('local_realignment', local), evidence('independent_view', view)]
    verdict, _, _, notes = verify_candidate(candidate(), ev, 'good')
    assert verdict == 'NEEDS_REVIEW'
    assert any('conflict' in n.lower() for n in notes)


def test_inconclusive_view_is_not_overridden_by_local_clearance():
    ev = [evidence('local_realignment', False), evidence('independent_view', None)]
    assert verify_candidate(candidate(), ev, 'good')[0] == 'NEEDS_REVIEW'


def test_old_unqualified_local_clearance_requires_review():
    ev = [dict(evidence_kind='local_realignment', source_tool='local_realignment',
               supports_defect=False, metrics={'reduction_ratio': 0.99})]
    assert verify_candidate(candidate(), ev, 'good')[0] == 'NEEDS_REVIEW'


def test_poor_registration_cannot_be_cleared_by_local_reprocessing():
    assert verify_candidate(candidate(), [evidence('local_realignment', False)], 'poor')[0] == 'NOT_EVALUABLE'


def test_failed_local_analysis_cannot_clear_an_illumination_suspect():
    ev = [evidence('local_realignment', None, reliable=False)]
    cand = dict(candidate(), illumination_suspect=True, structural_mismatch_score=0.1)
    assert verify_candidate(cand, ev, 'good')[0] == 'NEEDS_REVIEW'


def test_registration_does_not_expand_orb_after_poor_sift(monkeypatch):
    tried = []
    def keypoint(ref, test, detector):
        tried.append(detector)
        return reg.RegistrationResult(None, None, None, {'quality': 'poor', 'attempts': [detector]})
    monkeypatch.setattr(reg, '_keypoint_attempt', keypoint)
    monkeypatch.setattr(reg, '_ecc_attempt', lambda *a: reg.RegistrationResult(None, None, None, {'quality':'failed'}))
    assert not reg.register(texture(), texture()).ok
    assert tried == ['SIFT']


@pytest.mark.parametrize('warp,correlation', [
    (np.float32([[1, 0, 0], [0, 1, 0]]), 0.4),
    (np.float32([[1, 0, 20], [0, 1, 0]]), 0.99),
    (np.float32([[-1, 0, 0], [0, 1, 0]]), 0.99),
    (np.float32([[1, 0, np.nan], [0, 1, 0]]), 0.99),
    (np.float32([[1, 0, 0], [0, 1, 0]]), float('nan')),
])
def test_unreliable_local_transforms_have_no_vote_and_finite_metrics(monkeypatch, warp, correlation):
    import json
    monkeypatch.setattr(cv2, 'findTransformECC', lambda *a: (correlation, warp.copy()))
    outcome = rt.tool_local_realignment(context(texture(), texture()), 'R01', [100, 80, 40, 40])
    assert outcome.supports_defect is None
    assert outcome.metrics['comparison_reliable'] is False
    json.dumps(outcome.metrics, allow_nan=False)


def test_missing_candidate_support_is_not_replaced_by_context(monkeypatch):
    monkeypatch.setattr(cv2, 'findTransformECC', lambda *a: (0.99, np.eye(2, 3, dtype=np.float32)))
    ref = texture()
    valid = np.full_like(ref, 255)
    valid[80:120, 100:140] = 0
    outcome = rt.tool_local_realignment(context(ref, ref, valid), 'R01', [100, 80, 40, 40])
    assert outcome.supports_defect is None
    assert outcome.metrics['comparison_reliable'] is False
    assert outcome.metrics['common_valid_fraction'] == 0


def test_local_fit_excludes_candidate_from_its_input_mask(monkeypatch):
    def inspect_mask(template, image, warp, motion, criteria, mask, gaussian):
        # 24px context margin with 3px smoothing halo around the 40px core.
        assert not mask[21:67, 21:67].any()
        assert mask.any()
        return 0.99, warp
    monkeypatch.setattr(cv2, 'findTransformECC', inspect_mask)
    ref = texture()
    outcome = rt.tool_local_realignment(context(ref, ref), 'R01', [100, 80, 40, 40])
    assert outcome.supports_defect is None  # identical pixels do not prove a change was removed


def test_local_evidence_survives_persistence_and_report(tmp_path, monkeypatch):
    import asyncio
    import json
    from app import store
    from app.config import settings
    from app.tools.registry import InspectionToolbelt

    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    ref = texture()
    shifted = cv2.warpAffine(ref, np.float32([[1, 0, 2], [0, 1, -1]]), (320, 240))
    cand = dict(candidate(), bbox=[100, 80, 90, 70], status='SUSPECTED',
                tools_used=[], evidence=[], notes=[], region_id='R01')
    state = dict(id='ins_ecc_report',status='running',source='upload',config={'max_tool_calls':12},
                 images={},registration={'quality':'good'},candidates={'R01':cand},
                 events=[],review_requests=[],tool_calls_used=0,iterations=1)
    belt = InspectionToolbelt(state, persist=True)
    monkeypatch.setattr(belt, '_ensure_images', lambda: None)
    monkeypatch.setattr(belt, '_build_context', lambda: context(ref, shifted))

    async def inspect_and_report():
        await belt.inspect_region('R01', 'local_realignment')
        await belt.verify_candidate('R01')
        return await belt.generate_inspection_report()

    report = asyncio.run(inspect_and_report())
    stored = store.load_state(state['id'])
    entry = report['verdicts'][0]
    assert entry['region_id'] == 'R01' and entry['status'] == 'CLEARED'
    assert entry['evidence'][0]['metrics']['measurement_version'] == 'local_ecc_v2'
    assert stored['report'] == report
    seq = [e['seq'] for e in store.get_events(state['id'])]
    assert seq == list(range(1, len(seq)+1))
    json.dumps(report, allow_nan=False)


def test_qualified_clearance_does_not_hide_an_inconclusive_local_attempt():
    ev = [evidence('local_realignment', False), evidence('local_realignment', None, reliable=False)]
    assert verify_candidate(candidate(), ev, 'good')[0] == 'NEEDS_REVIEW'
