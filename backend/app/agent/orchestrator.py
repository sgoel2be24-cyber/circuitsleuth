"""Agentic active-perception orchestrator.

Bounded loop:  OBSERVE -> ALIGN -> DETECT -> ASSESS -> (PLAN -> ACT -> VERIFY)* -> DECIDE

The sequence is never hardcoded per scenario: every PLAN step re-scores all
open candidates from current measurements (`app.agent.policy`) and executes the
single best action through the same toolbelt that the MCP server exposes.
The loop terminates on: all regions decided / tool budget exhausted /
iteration budget exhausted / unrecoverable registration failure.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any, Callable

from ..tools.registry import InspectionToolbelt, ToolError
from ..agent import policy
from .. import store


async def run_inspection(
    state: dict[str, Any],
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Drive one inspection to completion. Mutates and persists `state`."""
    tb = InspectionToolbelt(state, _wrap_sink(event_sink), persist=True)
    state["status"] = "running"
    state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.perf_counter()

    async def set_stop(reason: str) -> None:
        state["stop_reason"] = reason

    try:
        # -------------------------------------------------------- OBSERVE
        imgs = state["images"]
        await tb._emit(
            "inspection_started",
            "Observation acquired: reference and test images loaded"
            + (", one secondary view available" if imgs.get("view2") else ", no secondary view available")
            + ".",
            phase="OBSERVE",
            evidence={"has_secondary_view": imgs.get("view2") is not None,
                      "scenario_id": state.get("scenario_id")},
        )

        # ---------------------------------------------------------- ALIGN
        result = await tb.align_images()
        if not result["ok"] and not tb._reg_recovery_tried:
            await tb._emit(
                "recovery_started",
                "Registration unreliable — attempting recovery with CLAHE-enhanced preprocessing.",
                phase="ALIGN",
                evidence={"attempt": "clahe_repreprocess"},
            )
            result = await tb.align_images(recovery=True)
        if not result["ok"]:
            # Refuse to fabricate: mark everything NOT_EVALUABLE.
            for rid, cand in state.get("candidates", {}).items():
                if cand["status"] == "SUSPECTED":
                    cand["status"] = "NOT_EVALUABLE"
                    cand["notes"].append("Registration failed; no defect claims possible.")
            await set_stop("registration_failed")
            await tb._emit(
                "inspection_aborted",
                "Registration failed after recovery. Inspection marked NOT_EVALUABLE — no defects reported.",
                phase="DECIDE",
                evidence={"registration_quality": result["quality"]},
            )
            return await _finalize(tb, state, t0)

        # --------------------------------------------------------- DETECT
        det = await tb.detect_defects()
        if det["candidate_count"] == 0:
            await set_stop("no_candidates")
            await tb._emit(
                "inspection_completed",
                "No suspicious regions detected — board appears clean under current observation quality.",
                phase="DECIDE",
                evidence={"candidate_count": 0},
            )
            return await _finalize(tb, state, t0)

        # ------------------------------------------- ASSESS/PLAN/ACT/VERIFY
        has_view2 = imgs.get("view2") is not None
        while True:
            state["iterations"] += 1
            if state["iterations"] > state["config"]["max_iterations"]:
                await set_stop("max_iterations_reached")
                break
            action = policy.choose_action(
                state["candidates"],
                (state.get("registration") or {}).get("quality", "failed"),
                has_view2,
            )
            if action is None:
                await set_stop("all_regions_decided")
                break
            rid, tool, score, breakdown = action
            open_count = sum(
                1 for c in state["candidates"].values() if c["status"] not in policy.TERMINAL_STATUSES
            )
            await tb._emit(
                "plan_selected",
                f"Planned {tool} for {rid} (priority {score:.2f}; {open_count} open region(s), "
                f"budget {state['tool_calls_used']}/{state['config']['max_tool_calls']} tool calls).",
                phase="PLAN",
                region_id=rid,
                evidence={"tool": tool, "priority_score": round(score, 3), "score_breakdown": breakdown,
                          "open_regions": open_count},
            )
            if state["tool_calls_used"] >= state["config"]["max_tool_calls"] and tool != "verify":
                await set_stop("tool_budget_exhausted")
                break

            if tool == "verify":
                await tb.verify_candidate(rid)
            elif tool in ("alternate_view", "request_additional_view"):
                res = await tb.request_additional_view(rid)
                if res.get("status") == "additional_capture_required":
                    await tb.request_human_review(
                        rid,
                        "Evidence inconclusive and no secondary view exists to disambiguate; new capture required.",
                        requested_action="capture a new image of this region or confirm/reject manually",
                    )
            else:
                await tb.inspect_region(rid, tool)

        # ----------------------------------------------- budget exhausted
        for rid, cand in state["candidates"].items():
            if cand["status"] not in policy.TERMINAL_STATUSES:
                cand["status"] = "NEEDS_REVIEW"
                cand["notes"].append("Inspection budget exhausted before verification completed.")
                await tb._emit(
                    "human_review_requested",
                    f"{rid} left unverified when the inspection budget ran out; escalated to human review.",
                    phase="DECIDE",
                    region_id=rid,
                    evidence={"reason": "budget_exhausted"},
                )

        await tb._emit(
            "inspection_completed",
            f"Inspection finished ({state['stop_reason']}): "
            f"{_counts_summary(state)}",
            phase="DECIDE",
            evidence={"stop_reason": state["stop_reason"], "verdicts": _verdicts(state)},
        )
        return await _finalize(tb, state, t0)

    except ToolError as exc:
        state["status"] = "failed"
        state["stop_reason"] = f"tool_error: {exc}"
        await tb._emit("inspection_failed", f"Tool error: {exc}", phase="DECIDE")
        store.save_state(state["id"], state)
        store.update_inspection(state["id"], status="failed")
        return state
    except Exception as exc:  # unrecoverable — surface honestly
        state["status"] = "failed"
        state["stop_reason"] = f"internal_error: {exc}"
        await tb._emit(
            "inspection_failed",
            f"Internal error: {exc}",
            phase="DECIDE",
            evidence={"traceback": traceback.format_exc(limit=6)},
        )
        store.save_state(state["id"], state)
        store.update_inspection(state["id"], status="failed")
        return state


async def _finalize(tb: InspectionToolbelt, state: dict[str, Any], t0: float) -> dict[str, Any]:
    report = await tb.generate_inspection_report()
    state["status"] = "completed"
    state["duration_s"] = round(time.perf_counter() - t0, 3)
    _sync_summary(state)
    store.save_state(state["id"], state)
    store.update_inspection(
        state["id"], status="completed", summary=_public_summary(state), report=report
    )
    await tb._emit(
        "report_ready",
        f"Report ready in {state['duration_s']}s using {state['tool_calls_used']} tool call(s).",
        phase="DECIDE",
        evidence={"duration_s": state["duration_s"], "tool_calls": state["tool_calls_used"]},
    )
    return state


def _verdicts(state: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in state.get("candidates", {}).values():
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out


def _counts_summary(state: dict[str, Any]) -> str:
    v = _verdicts(state) or {}
    parts = [f"{k.replace('_', ' ').lower()}={n}" for k, n in sorted(v.items())]
    return ", ".join(parts) if parts else "no regions"


def _public_summary(state: dict[str, Any]) -> dict[str, Any]:
    v = _verdicts(state)
    return {
        "id": state["id"],
        "created_at": state["created_at"],
        "status": state["status"],
        "source": state["source"],
        "scenario_id": state.get("scenario_id"),
        "config": state["config"],
        "candidate_count": len(state.get("candidates", {})),
        "confirmed": v.get("CONFIRMED_DEFECT", 0),
        "likely": v.get("LIKELY_DEFECT", 0),
        "cleared": v.get("CLEARED", 0),
        "needs_review": v.get("NEEDS_REVIEW", 0),
        "not_evaluable": v.get("NOT_EVALUABLE", 0),
        "tool_calls_used": state["tool_calls_used"],
        "duration_s": state.get("duration_s"),
        "stop_reason": state.get("stop_reason"),
    }


def _sync_summary(state: dict[str, Any]) -> None:
    state["summary"] = _public_summary(state)


def _wrap_sink(sink: Callable[[dict], Any] | None):
    if sink is None:
        return None

    async def _s(ev: dict) -> None:
        out = sink(ev)
        if asyncio.iscoroutine(out):
            await out

    return _s
