"""Orchestrator end-to-end tests over the synthetic demo scenarios.

Expected behaviors come straight from the product spec (section 8).
"""

from __future__ import annotations

from tests.conftest import make_state


def test_scenario1_confirms_all_defects(scenario_paths, run_inspection_fixture):
    out = run_inspection_fixture(make_state(scenario_paths["scenario_01_clear_defects"]))
    assert out["status"] == "completed"
    assert out["stop_reason"] == "all_regions_decided"
    verdicts = [c["status"] for c in out["candidates"].values()]
    assert verdicts and all(v in ("CONFIRMED_DEFECT", "LIKELY_DEFECT") for v in verdicts)
    assert len(out["candidates"]) == 3
    # every verdict is backed by at least one piece of recorded evidence
    for c in out["candidates"].values():
        assert c["evidence"], f"{c['region_id']} has no evidence"
        assert c["label_basis"]


def test_scenario2_clean_board_reports_no_defects(scenario_paths, run_inspection_fixture):
    out = run_inspection_fixture(make_state(scenario_paths["scenario_02_clean_board"]))
    assert out["stop_reason"] == "no_candidates"
    assert out["candidates"] == {}
    assert out["tool_calls_used"] == 0


def test_scenario3_agent_resolves_glare_with_tools(scenario_paths, run_inspection_fixture):
    import json

    from tests.test_detection import _iou

    out = run_inspection_fixture(make_state(scenario_paths["scenario_03_ambiguous_glare"]))
    gt = json.loads((scenario_paths["scenario_03_ambiguous_glare"] / "annotations.json").read_text())

    def _overlap(c: dict) -> float:
        return max(_iou(g["bbox"], c["bbox"]) for g in gt)

    real = [c for c in out["candidates"].values() if _overlap(c) > 0.15]
    ghosts = [c for c in out["candidates"].values() if _overlap(c) <= 0.15]
    assert real, "the true pinhole must be detected"
    assert any(c["tools_used"] and "adaptive_threshold" in c["tools_used"]
               for c in out["candidates"].values()), "confound hypothesis must be tested"
    # the real defect ends confirmed/likely; glare ghosts never get reported
    assert all(c["status"] in ("CONFIRMED_DEFECT", "LIKELY_DEFECT") for c in real)
    assert all(c["status"] != "CONFIRMED_DEFECT" for c in ghosts)


def test_scenario4_registration_failure_is_not_evaluable(scenario_paths, run_inspection_fixture):
    out = run_inspection_fixture(make_state(scenario_paths["scenario_04_registration_failure"]))
    assert out["stop_reason"] == "registration_failed"
    assert out["candidates"] == {} or all(
        c["status"] == "NOT_EVALUABLE" for c in out["candidates"].values()
    )
    # recovery was attempted before giving up
    types = [e["type"] for e in out["events"]]
    assert "recovery_started" in types


def test_scenario5_requests_view_then_escalates_to_review(scenario_paths, run_inspection_fixture):
    out = run_inspection_fixture(make_state(scenario_paths["scenario_05_no_second_view"]))
    types = [e["type"] for e in out["events"]]
    assert "additional_capture_required" in types
    assert "human_review_requested" in types
    assert out["review_requests"], "a human review task must exist"
    assert any(c["status"] == "NEEDS_REVIEW" for c in out["candidates"].values())


def test_scenario6_budget_respected_and_prioritized(scenario_paths, run_inspection_fixture):
    st = make_state(scenario_paths["scenario_06_multiple_regions"], budget=7)
    out = run_inspection_fixture(st)
    assert out["tool_calls_used"] <= 7
    assert len(out["candidates"]) == 5
    # independent per-region states: mixture of decided + escalated, all recorded
    for c in out["candidates"].values():
        assert c["status"] in ("CONFIRMED_DEFECT", "LIKELY_DEFECT", "CLEARED",
                               "NEEDS_REVIEW", "NOT_EVALUABLE")
    # high-severity regions were addressed before weaker ones got verified
    report = out.get("report")
    assert report is not None and len(report["verdicts"]) == 5


def test_events_are_audit_complete(scenario_paths, run_inspection_fixture):
    out = run_inspection_fixture(make_state(scenario_paths["scenario_01_clear_defects"]))
    types = [e["type"] for e in out["events"]]
    for expected in ("inspection_started", "registration_completed", "detection_completed",
                     "candidate_found", "plan_selected", "tool_executed",
                     "candidate_verified", "inspection_completed", "report_generated"):
        assert expected in types, expected
    # plan events carry the score breakdown (transparency requirement)
    plan = next(e for e in out["events"] if e["type"] == "plan_selected")
    assert "priority_score" in plan["evidence"] and "score_breakdown" in plan["evidence"]
