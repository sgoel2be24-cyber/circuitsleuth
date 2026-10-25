"""Inspection toolbelt: the single source of truth for agent tools.

The same async methods back
  * the orchestrator's internal loop, and
  * the MCP server (`app.tools.mcp_server`) that exposes them to any
    MCP-compatible client.

Every method: validated inputs, JSON-safe structured output, explicit failure
statuses, persisted events with timestamps, and bounded execution.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import cv2
import numpy as np

from ..config import settings
from ..cv import detection as det_mod
from ..cv import region_tools as rt
from ..cv import registration as reg_mod
from ..cv import verification as ver_mod
from ..cv.imaging import load_bgr, save_png, to_grayscale
from ..cv.preprocess import PreprocessParams, preprocess
from .. import store

EventSink = Callable[[dict[str, Any]], Awaitable[None]]


def _now() -> float:
    return time.time()


class ToolError(RuntimeError):
    pass


class InspectionToolbelt:
    """Stateful tool implementations bound to one inspection run."""

    def __init__(
        self,
        state: dict[str, Any],
        event_sink: EventSink | None = None,
        *,
        persist: bool = True,
    ) -> None:
        self.state = state
        self.event_sink = event_sink
        self.persist = persist
        self._seq = 0
        self._lock = asyncio.Lock()
        # runtime (non-persisted) caches
        self._ref_gray: np.ndarray | None = None
        self._test_gray: np.ndarray | None = None
        self._reg: reg_mod.RegistrationResult | None = None
        self._view2_gray: np.ndarray | None = None
        self._view2_reg: reg_mod.RegistrationResult | None = None
        self._reg_recovery_tried = False
        self._params = PreprocessParams()

    # ------------------------------------------------------------------ util

    async def _emit(
        self,
        etype: str,
        message: str,
        *,
        phase: str = "ACT",
        evidence: dict | None = None,
        region_id: str | None = None,
        artifacts: list[str] | None = None,
    ) -> None:
        self._seq += 1
        ev = {
            "seq": self._seq,
            "ts": _now(),
            "phase": phase,
            "type": etype,
            "message": message,
            "evidence": evidence or {},
            "region_id": region_id,
            "artifacts": artifacts or [],
        }
        self.state.setdefault("events", []).append(ev)
        if self.persist:
            store.append_event(self.state["id"], ev)
        if self.event_sink is not None:
            await self.event_sink(ev)

    def _save_artifact(self, name: str, img: np.ndarray) -> str:
        import cv2 as _cv

        ok, buf = _cv.imencode(".png", img)
        if not ok:
            return name
        return store.save_artifact(self.state["id"], name, buf.tobytes())

    def _save_state(self) -> None:
        if self.persist:
            store.save_state(self.state["id"], self.state)

    # ------------------------------------------------------------- images

    def _ensure_images(self) -> None:
        if self._ref_gray is not None:
            return
        imgs = self.state["images"]
        ref = to_grayscale(load_bgr(imgs["reference"]))
        test = to_grayscale(load_bgr(imgs["test"]))
        # register() applies registration preprocessing internally; keep raw
        # grays for it and separately-preprocessed copies for detection.
        self._ref_gray = ref
        self._test_gray = test
        self._ref_det = preprocess(ref, self._params, for_registration=False)
        if imgs.get("view2"):
            self._view2_gray = preprocess(to_grayscale(load_bgr(imgs["view2"])), self._params, for_registration=False)

    # ------------------------------------------------------------------ tools

    async def get_inspection_context(self) -> dict[str, Any]:
        """Return current inspection state, candidates and available views."""
        self._ensure_images()
        cands = self.state.get("candidates", {})
        return {
            "inspection_id": self.state["id"],
            "status": self.state["status"],
            "registration": self.state.get("registration"),
            "detection": self.state.get("detection"),
            "candidates": {rid: _candidate_public(c) for rid, c in cands.items()},
            "available_views": {
                "reference": True,
                "test": True,
                "secondary": self.state["images"].get("view2") is not None,
            },
            "budget": {
                "tool_calls_used": self.state["tool_calls_used"],
                "max_tool_calls": self.state["config"]["max_tool_calls"],
                "iterations": self.state["iterations"],
                "max_iterations": self.state["config"]["max_iterations"],
            },
        }

    async def align_images(self, *, recovery: bool = False) -> dict[str, Any]:
        """Align test -> reference. `recovery=True` retries with CLAHE-enhanced
        preprocessing after a failed first attempt."""
        self._ensure_images()
        phase = "ALIGN"
        params = PreprocessParams(use_clahe_for_registration=True) if recovery else self._params
        self._reg_recovery_tried = self._reg_recovery_tried or recovery
        t0 = _now()
        reg = reg_mod.register(self._ref_gray, self._test_gray, params)
        metrics = reg.metrics
        duration = round(_now() - t0, 3)
        self.state["registration"] = metrics
        self.state.setdefault("timing", {})["registration_s"] = duration
        if reg.ok:
            self._reg = reg
            await self._emit(
                "registration_completed",
                f"Aligned test to reference with {metrics['detector']} "
                f"({metrics.get('inliers', 'n/a')} inliers, residual {metrics.get('mean_residual_px', 'n/a')}px, quality {metrics['quality']}).",
                phase=phase,
                evidence=metrics,
            )
            self._save_state()
            return {"ok": True, "quality": metrics["quality"], "metrics": metrics}
        await self._emit(
            "registration_failed",
            f"Registration {metrics['quality']}: {metrics.get('failure_reason')}",
            phase=phase,
            evidence=metrics,
        )
        self._save_state()
        return {"ok": False, "quality": metrics["quality"], "metrics": metrics}

    async def detect_defects(self) -> dict[str, Any]:
        if self._reg is None or not self._reg.ok:
            raise ToolError("detect_defects requires successful alignment")
        self._ensure_images()
        t0 = _now()
        result = det_mod.detect_candidates(self._ref_det, self._reg.warped_test, self._reg.valid_mask)
        duration = round(_now() - t0, 3)

        heatmap = self._save_artifact("diff_heatmap", det_mod.diff_heatmap(result.diff_map, self._reg.valid_mask))
        overlay = self._render_overlay(result)
        overlay_name = self._save_artifact("candidate_overlay", overlay)

        candidates: dict[str, dict] = {}
        for i, c in enumerate(result.candidates, start=1):
            rid = f"R{i:02d}"
            candidates[rid] = {
                "region_id": rid,
                "bbox": c["bbox"],
                "area_px": c["area_px"],
                "centroid": c["centroid"],
                "difference_score": c["difference_score"],
                "structural_mismatch_score": c["structural_mismatch_score"],
                "evidence_quality_score": c["evidence_quality_score"],
                "edge_delta": c["edge_delta"],
                "touches_invalid_warp_region": c["touches_invalid_warp_region"],
                "illumination_suspect": c["illumination_suspect"],
                "added_on_flat_background": c["added_on_flat_background"],
                "status": "SUSPECTED",
                "label": None,
                "label_basis": None,
                "evidence": [],
                "tools_used": [],
                "notes": [],
            }
        self.state["candidates"] = candidates
        self.state["detection"] = {
            "params": result.params,
            "candidate_count": len(candidates),
            "artifacts": {"diff_heatmap": heatmap, "candidate_overlay": overlay_name},
        }
        self.state.setdefault("timing", {})["detection_s"] = duration
        await self._emit(
            "detection_completed",
            f"Detected {len(candidates)} suspicious region(s).",
            phase="DETECT",
            evidence={"candidate_count": len(candidates), "params": result.params},
            artifacts=[heatmap, overlay_name],
        )
        for rid, c in candidates.items():
            await self._emit(
                "candidate_found",
                f"Region {rid} at {tuple(c['bbox'])}: difference {c['difference_score']:.2f}, "
                f"mismatch {c['structural_mismatch_score']:.2f}"
                + (", illumination-suspect" if c["illumination_suspect"] else "")
                + (", at warp border" if c["touches_invalid_warp_region"] else ""),
                phase="DETECT",
                region_id=rid,
                evidence={"bbox": c["bbox"], "difference_score": c["difference_score"],
                          "structural_mismatch_score": c["structural_mismatch_score"],
                          "illumination_suspect": c["illumination_suspect"]},
            )
        self._save_state()
        return {"candidate_count": len(candidates), "candidates": candidates}

    def _render_overlay(self, result: det_mod.DetectionResult) -> np.ndarray:
        base_img = self._ref_gray if self._ref_gray is not None else result.diff_map
        base = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGR)
        return cv2.addWeighted(base, 0.8, cv2.cvtColor(result.candidate_mask, cv2.COLOR_GRAY2BGR), 0.4, 0)

    async def inspect_region(self, region_id: str, tool: str) -> dict[str, Any]:
        """Run a secondary analysis on a candidate region."""
        self._ensure_images()
        cand = self.state.get("candidates", {}).get(region_id)
        if cand is None:
            raise ToolError(f"unknown region {region_id!r}")
        if tool not in rt.TOOL_FUNCTIONS:
            raise ToolError(f"unknown tool {tool!r}; available: {sorted(rt.TOOL_FUNCTIONS)}")
        if self.state["tool_calls_used"] >= self.state["config"]["max_tool_calls"]:
            return {"ok": False, "error": "tool budget exhausted"}

        ctx = self._build_context()
        t0 = _now()
        outcome = rt.TOOL_FUNCTIONS[tool](ctx, region_id, cand["bbox"])
        duration = round(_now() - t0, 3)
        self.state["tool_calls_used"] += 1

        artifacts: list[str] = []
        for name, img in outcome.artifacts.items():
            artifacts.append(self._save_artifact(f"{region_id.lower()}_{name}", img))

        evidence_entry = {
            "evidence_kind": outcome.evidence_kind,
            "source_tool": outcome.tool,
            "summary": outcome.summary,
            "metrics": _jsonify(outcome.metrics),
            "supports_defect": outcome.supports_defect,
            "artifact": artifacts[0] if artifacts else None,
            "timestamp": _now(),
            "duration_s": duration,
            "honesty": outcome.honesty,
        }
        cand["evidence"].append(evidence_entry)
        if outcome.tool not in cand["tools_used"]:
            cand["tools_used"].append(outcome.tool)

        await self._emit(
            "tool_executed",
            f"{tool} on {region_id}: {outcome.summary}",
            phase="ACT",
            region_id=region_id,
            evidence={"tool": tool, "supports_defect": outcome.supports_defect,
                      "honesty": outcome.honesty, "metrics": evidence_entry["metrics"],
                      "duration_s": duration},
            artifacts=artifacts,
        )
        self._save_state()
        return {"ok": True, "evidence": evidence_entry, "artifacts": artifacts}

    def _build_context(self) -> rt.ToolContext:
        self._ensure_images()
        if self._reg is None or not self._reg.ok:
            raise ToolError("tool context requires successful alignment")
        diff = cv2.absdiff(self._ref_det, self._reg.warped_test)
        ncc = det_mod.local_ncc(self._ref_det, self._reg.warped_test)
        secondary_aligned = None
        secondary_valid = None
        if self._view2_gray is not None:
            if self._view2_reg is None or not self._view2_reg.ok:
                self._view2_reg = reg_mod.register(self._ref_det, self._view2_gray, self._params)
            if self._view2_reg.ok:
                secondary_aligned = self._view2_reg.warped_test
                secondary_valid = self._view2_reg.valid_mask
        return rt.ToolContext(
            ref_gray=self._ref_det,
            test_aligned=self._reg.warped_test,
            test_original=self._reg.warped_test,
            valid_mask=self._reg.valid_mask,
            diff_map=diff,
            mismatch_map=(1.0 - ncc),
            secondary_view_gray=self._view2_gray,
            secondary_aligned=secondary_aligned,
            secondary_valid_mask=secondary_valid,
        )

    async def request_additional_view(self, region_id: str) -> dict[str, Any]:
        """Select the secondary captured view for a region, or report that a
        new capture is required when none exists."""
        cand = self.state.get("candidates", {}).get(region_id)
        if cand is None:
            raise ToolError(f"unknown region {region_id!r}")
        if self.state["images"].get("view2") is None:
            if "request_additional_view" not in cand["tools_used"]:
                cand["tools_used"].append("request_additional_view")
            self.state["tool_calls_used"] += 1
            await self._emit(
                "additional_capture_required",
                f"No secondary view exists for {region_id}; a new capture is required.",
                phase="ACT",
                region_id=region_id,
                evidence={"secondary_view_available": False},
            )
            self._save_state()
            return {"ok": True, "status": "additional_capture_required", "secondary_view_available": False}
        result = await self.inspect_region(region_id, "alternate_view")
        return {"ok": True, "status": "compared", "result": result}

    async def verify_candidate(self, region_id: str) -> dict[str, Any]:
        """Combine all evidence for a region into a final verdict."""
        cand = self.state.get("candidates", {}).get(region_id)
        if cand is None:
            raise ToolError(f"unknown region {region_id!r}")
        reg_quality = (self.state.get("registration") or {}).get("quality", "failed")
        verdict, label, basis, notes = ver_mod.verify_candidate(cand, cand["evidence"], reg_quality)
        cand["status"] = verdict
        cand["label"] = label
        cand["label_basis"] = basis
        cand["notes"].extend(notes)
        await self._emit(
            "candidate_verified",
            f"{region_id} -> {verdict}"
            + (f" ({label})" if label else "")
            + f"; basis: {basis}",
            phase="VERIFY",
            region_id=region_id,
            evidence={"verdict": verdict, "label": label, "basis": basis, "notes": notes,
                      "evidence_count": len(cand["evidence"])},
        )
        self._save_state()
        return {"ok": True, "verdict": verdict, "label": label, "notes": notes}

    async def request_human_review(
        self, region_id: str, reason: str, requested_action: str = "operator confirmation"
    ) -> dict[str, Any]:
        cand = self.state.get("candidates", {}).get(region_id)
        if cand is None:
            raise ToolError(f"unknown region {region_id!r}")
        review = {
            "region_id": region_id,
            "reason": reason,
            "requested_action": requested_action,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "bbox": cand["bbox"],
        }
        self.state.setdefault("review_requests", []).append(review)
        if cand["status"] not in ("NEEDS_REVIEW",):
            cand["status"] = "NEEDS_REVIEW"
        await self._emit(
            "human_review_requested",
            f"Human review requested for {region_id}: {reason}",
            phase="DECIDE",
            region_id=region_id,
            evidence=review,
        )
        self._save_state()
        return {"ok": True, "review": review}

    async def generate_inspection_report(self) -> dict[str, Any]:
        from ..schemas import InspectionReport, ReportVerdict, BBox, ReviewRequest

        cands = self.state.get("candidates", {})
        verdicts = []
        for rid, c in cands.items():
            bx = c["bbox"]
            verdicts.append(
                ReportVerdict(
                    region_id=rid,
                    bbox=BBox(x=int(bx[0]), y=int(bx[1]), w=int(bx[2]), h=int(bx[3])),
                    status=c["status"],
                    label=c.get("label"),
                    label_basis=c.get("label_basis"),
                    difference_score=c["difference_score"],
                    structural_mismatch_score=c["structural_mismatch_score"],
                    evidence=c["evidence"],
                    tools_used=c["tools_used"],
                    notes=c.get("notes", []),
                )
            )
        reviews = [ReviewRequest(**r) for r in self.state.get("review_requests", [])]
        reg = self.state.get("registration")
        report = InspectionReport(
            inspection_id=self.state["id"],
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            registration=reg,
            verdicts=verdicts,
            review_requests=reviews,
            tool_calls_used=self.state["tool_calls_used"],
            iterations=self.state["iterations"],
            stop_reason=self.state.get("stop_reason", "unknown"),
            limitations=LIMITATIONS,
        )
        data = report.model_dump()
        self.state["report"] = data
        await self._emit(
            "report_generated",
            f"Inspection report generated: {len(verdicts)} regions assessed.",
            phase="DECIDE",
            evidence={"verdict_counts": _verdict_counts(cands)},
        )
        self._save_state()
        return data


LIMITATIONS = [
    "Synthetic demo data: benchmark numbers describe the generated dataset, not production PCBs.",
    "Anomaly detection is reference-based; classification labels are heuristic and hedged.",
    "Heuristic scores are quality measures, not calibrated probabilities.",
    "A crop-based secondary tool reprocesses existing pixels; only an alternate view adds new optical evidence.",
]


def _jsonify(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _verdict_counts(cands: dict[str, dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in cands.values():
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return counts


def _candidate_public(c: dict[str, Any]) -> dict[str, Any]:
    return _jsonify(c)
