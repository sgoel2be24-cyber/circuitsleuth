"""Deterministic planning policy for the active-perception loop.

The planner scores every (region, action) pair and picks the maximum. The
score is a documented heuristic — every term is measurable and logged so the
UI can show *why* the agent chose an action.

    priority = W_U * uncertainty
             + W_S * severity
             + W_Q * (1 - evidence_quality)
             + W_G * expected_information_gain
             - W_C * tool_cost
             - repeat_penalty

Weights are constants on purpose: a transparent baseline policy that judges
can audit. An LLM planner could later *propose* arguments, but the same
schema-validated tool set bounds what it can do.
"""

from __future__ import annotations

from typing import Any

W_UNCERTAINTY = 2.0
W_SEVERITY = 1.5
W_QUALITY = 0.8
W_GAIN = 1.2
W_COST = 0.6
W_CLOSEOUT = 1.0     # bonus for regions with decisive evidence awaiting verification
REPEAT_PENALTY = 0.8

# Estimated relative execution cost per tool (latency proxy, documented).
TOOL_COST = {
    "highres_zoom": 0.2,
    "edge_topology": 0.3,
    "adaptive_threshold": 0.3,
    "local_realignment": 0.6,
    "alternate_view": 0.5,
    "request_capture": 0.9,
    "verify": 0.1,
}

TERMINAL_STATUSES = {"CONFIRMED_DEFECT", "LIKELY_DEFECT", "CLEARED", "NEEDS_REVIEW", "NOT_EVALUABLE"}


def candidate_uncertainty(cand: dict[str, Any], registration_quality: str) -> float:
    if cand["status"] in TERMINAL_STATUSES:
        return 0.0
    u = 1.0
    if cand.get("illumination_suspect"):
        u += 0.5
    if cand.get("touches_invalid_warp_region"):
        u += 0.5
    if registration_quality == "marginal":
        u += 0.25
    return min(u, 2.0)


def priority_score(
    cand: dict[str, Any],
    tool: str,
    registration_quality: str,
    tools_used_count: int,
) -> tuple[float, dict[str, float]]:
    """Return (score, breakdown) for a (region, tool) action."""
    uncertainty = candidate_uncertainty(cand, registration_quality)
    severity = min(1.0, float(cand.get("difference_score", 0.0)) * 2.0)
    quality = float(cand.get("evidence_quality_score", 0.0))
    gain = 1.0 if tool not in cand.get("tools_used", []) else 0.1
    cost = TOOL_COST.get(tool, 0.5)
    repeat = REPEAT_PENALTY * tools_used_count
    closeout = W_CLOSEOUT if _has_decisive_evidence(cand) and tool == "verify" else 0.0
    score = (
        W_UNCERTAINTY * uncertainty
        + W_SEVERITY * severity
        + W_QUALITY * (1.0 - quality)
        + W_GAIN * gain
        - W_COST * cost
        - repeat
        + closeout
    )
    return score, {
        "uncertainty": round(uncertainty, 3),
        "severity": round(severity, 3),
        "evidence_quality": round(quality, 3),
        "info_gain": round(gain, 3),
        "cost": cost,
        "repeat_penalty": round(repeat, 3),
        "closeout_bonus": closeout,
    }


def _has_decisive_evidence(cand: dict[str, Any]) -> bool:
    """True when some tool already returned a signal that verification should
    consume immediately (independent view compared, realignment cleared the
    candidate, or adaptive thresholding proved an illumination confound)."""
    for e in cand.get("evidence", []):
        if e.get("evidence_kind") == "independent_view" and e.get("supports_defect") is not None:
            return True
        if e.get("evidence_kind") == "local_realignment" and e.get("supports_defect") is False:
            return True
        if e.get("source_tool") == "adaptive_threshold" and (e.get("metrics") or {}).get("illumination_confound_likely"):
            return True
    return False


def choose_tool(cand: dict[str, Any], has_secondary_view: bool) -> str:
    """Evidence-driven tool selection for a region (ordered hypothesis tests).

    0. A tool already produced a decisive signal -> verify now.
    1. Candidate sits at the warp border / registration is suspect
       -> test the misalignment hypothesis first (local ECC).
    2. Cheap confound test first, for every candidate: adaptive-threshold
       comparison is invariant to smooth illumination (glare/shadow) and
       costs little. If it proves a pure illumination confound, verification
       can clear the region without spending the independent view.
    3. Independent evidence: consult an existing secondary view, or — when
       none exists — formally request one (the tool reports capture-required
       and the planner escalates to human review).
    4. Characterize geometry with edge topology, then magnified reprocessing.
    5. Everything applied -> verify.
    """
    used = set(cand.get("tools_used", []))
    if used and _has_decisive_evidence(cand):
        return "verify"
    if (cand.get("touches_invalid_warp_region") or cand.get("local_alignment_suspect")) \
            and "local_realignment" not in used:
        return "local_realignment"
    # Cheap confound test first when the candidate could plausibly be an
    # illumination artifact; strong structural evidence goes straight to the
    # independent view to conserve budget.
    if "adaptive_threshold" not in used and (
        cand.get("illumination_suspect") or float(cand.get("structural_mismatch_score", 1.0)) < 0.5
    ):
        return "adaptive_threshold"
    if "alternate_view" not in used and "request_additional_view" not in used:
        return "alternate_view" if has_secondary_view else "request_additional_view"
    if "edge_topology" not in used:
        return "edge_topology"
    if "highres_zoom" not in used:
        return "highres_zoom"
    return "verify"


def choose_action(
    candidates: dict[str, dict[str, Any]],
    registration_quality: str,
    has_secondary_view: bool,
) -> tuple[str, str, float, dict[str, float]] | None:
    """Pick the highest-priority (region_id, tool) among open candidates.

    Returns None when every candidate is terminal (nothing left to do).
    """
    best: tuple[str, str, float, dict[str, float]] | None = None
    for rid, cand in candidates.items():
        if cand["status"] in TERMINAL_STATUSES:
            continue
        tool = choose_tool(cand, has_secondary_view)
        score, breakdown = priority_score(cand, tool, registration_quality, len(cand.get("tools_used", [])))
        if best is None or score > best[2]:
            best = (rid, tool, score, breakdown)
    return best
