"""Policy and orchestrator behavior tests."""

from __future__ import annotations

from app.agent import policy


def test_priority_prefers_uncertain_strong_candidates():
    strong = {"region_id": "A", "difference_score": 0.4, "evidence_quality_score": 0.8,
              "status": "SUSPECTED", "tools_used": [], "illumination_suspect": False}
    weak = {"region_id": "B", "difference_score": 0.1, "evidence_quality_score": 0.2,
            "status": "SUSPECTED", "tools_used": [], "illumination_suspect": False}
    action = policy.choose_action({"A": strong, "B": weak}, "good", False)
    assert action is not None and action[0] == "A"


def test_terminal_candidates_never_selected():
    done = {"region_id": "A", "difference_score": 0.4, "evidence_quality_score": 0.9,
            "status": "CONFIRMED_DEFECT", "tools_used": ["alternate_view"]}
    open_c = {"region_id": "B", "difference_score": 0.2, "evidence_quality_score": 0.5,
              "status": "SUSPECTED", "tools_used": []}
    action = policy.choose_action({"A": done, "B": open_c}, "good", False)
    assert action is not None and action[0] == "B"


def test_no_action_when_all_terminal():
    done = {"region_id": "A", "difference_score": 0.4, "evidence_quality_score": 0.9,
            "status": "CLEARED", "tools_used": ["alternate_view"]}
    assert policy.choose_action({"A": done}, "good", False) is None


def test_decisive_evidence_triggers_verify():
    cand = {"region_id": "A", "difference_score": 0.3, "evidence_quality_score": 0.7,
            "status": "SUSPECTED", "tools_used": ["alternate_view"],
            "evidence": [{"evidence_kind": "independent_view", "source_tool": "alternate_view",
                          "supports_defect": True, "metrics": {}}]}
    assert policy.choose_tool(cand, True) == "verify"


def test_illumination_suspect_routes_adaptive_threshold():
    cand = {"region_id": "A", "difference_score": 0.3, "evidence_quality_score": 0.7,
            "status": "SUSPECTED", "tools_used": [], "illumination_suspect": True}
    assert policy.choose_tool(cand, False) == "adaptive_threshold"


def test_no_secondary_view_routes_request():
    cand = {"region_id": "A", "difference_score": 0.3, "evidence_quality_score": 0.7,
            "status": "SUSPECTED", "tools_used": ["adaptive_threshold"],
            "illumination_suspect": False, "structural_mismatch_score": 0.6,
            "evidence": []}
    assert policy.choose_tool(cand, False) == "request_additional_view"


def test_tool_costs_documented():
    for t in ("highres_zoom", "edge_topology", "adaptive_threshold",
              "local_realignment", "alternate_view"):
        assert t in policy.TOOL_COST
