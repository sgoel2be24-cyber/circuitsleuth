"""Reproducible evaluation: Baseline (fixed single pass) vs CircuitSleuth (adaptive).

For each scenario template we generate N statistically independent synthetic
variants (seeded board layouts, defects, illumination, noise). Each variant is
run through:

  Baseline A   — fixed pipeline: register -> detect -> rule verdict from the
                 detection scores alone. No secondary tools, no re-processing.
  CircuitSleuth — the full active-perception agent (same OpenCV core, plus
                 dynamically selected secondary tools and verification).

Metrics where annotations permit: precision / recall / F1 on defect
localization (IoU >= 0.15 with ground truth), false-positive counts on clean
boards, verdict breakdowns, escalation rate, tool calls, wall-clock latency.

Everything is synthetic and clearly labeled as such.

Usage:  python evaluation/benchmark.py [--variants 5] [--out evaluation]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.cv.detection import DetectionParams, detect_candidates  # noqa: E402
from app.cv.imaging import load_bgr, to_grayscale  # noqa: E402
from app.cv.preprocess import PreprocessParams, preprocess  # noqa: E402
from app.cv.registration import register  # noqa: E402
from app.cv.verification import MODERATE_DIFF, MODERATE_MISMATCH, STRONG_DIFF, STRONG_MISMATCH, _classify  # noqa: E402
from app.agent.orchestrator import run_inspection  # noqa: E402
from tools.generate_dataset import SCENARIO_IDS, build_scenario  # noqa: E402


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / (aw * ah + bw * bh - inter)


def make_state(images: dict, scenario_id: str, variant: int, budget: int) -> dict:
    return {
        "id": f"bench_{scenario_id}_v{variant}",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "created",
        "source": "benchmark",
        "scenario_id": scenario_id,
        "config": {"max_tool_calls": budget, "max_iterations": 24,
                   "require_independent_view_for_confirm": False},
        "images": images,
        "candidates": {},
        "tool_calls_used": 0,
        "iterations": 0,
        "review_requests": [],
        "events": [],
    }


def baseline_run(scenario_dir: Path) -> dict:
    """Fixed single-pass pipeline: register, detect, rule verdict. No tools."""
    t0 = time.perf_counter()
    ref = to_grayscale(load_bgr(scenario_dir / "reference.png"))
    test = to_grayscale(load_bgr(scenario_dir / "test.png"))
    p = PreprocessParams()
    reg = register(ref, test, p)
    cands: list[dict] = []
    if reg.ok:
        det = detect_candidates(
            preprocess(ref, p, for_registration=False), reg.warped_test, reg.valid_mask, DetectionParams()
        )
        for c in det.candidates:
            cand = dict(c)
            diff, mm = c["difference_score"], c["structural_mismatch_score"]
            strong = diff >= STRONG_DIFF and mm >= STRONG_MISMATCH
            moderate = diff >= MODERATE_DIFF or mm >= MODERATE_MISMATCH
            if reg.quality in ("poor", "failed"):
                verdict, label = "NOT_EVALUABLE", None
            elif c["touches_invalid_warp_region"]:
                verdict, label = "NOT_EVALUABLE", None
            elif strong and c["evidence_quality_score"] >= 0.35:
                verdict, label = "CONFIRMED_DEFECT", _classify(c, [])[0]
            elif c.get("illumination_suspect"):
                verdict, label = "CLEARED", None
            elif moderate:
                verdict, label = "LIKELY_DEFECT", _classify(c, [])[0]
            else:
                verdict, label = "NEEDS_REVIEW", None
            cand["status"] = verdict
            cand["label"] = label
            cands.append(cand)
    return {
        "registration_quality": reg.metrics.get("quality"),
        "candidates": cands,
        "latency_s": round(time.perf_counter() - t0, 3),
        "tool_calls": 0,
    }


def score_variant(gt: list[dict], cands: list[dict], verdict_level: bool = False) -> dict:
    """Localization P/R/F1. With verdict_level=True only candidates whose final
    verdict claims a defect (CONFIRMED/LIKELY) count as reported positives —
    the operationally meaningful metric (cleared confounds are not alarms)."""
    if verdict_level:
        cands = [c for c in cands if c.get("status") in ("CONFIRMED_DEFECT", "LIKELY_DEFECT")]
    matched_gt = set()
    tp, fp = 0, 0
    for c in cands:
        best, bi = 0.0, -1
        for i, g in enumerate(gt):
            v = iou(g["bbox"], c["bbox"])
            if v > best:
                best, bi = v, i
        if best >= 0.15 and bi not in matched_gt:
            matched_gt.add(bi)
            tp += 1
        else:
            fp += 1
    fn = len(gt) - len(matched_gt)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4),
            "recall": round(recall, 4), "f1": round(f1, 4)}


def verdict_counts(cands: list[dict]) -> dict:
    out: dict[str, int] = {}
    for c in cands:
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out


def run_benchmark(n_variants: int, out_dir: Path) -> dict:
    work = out_dir / "bench_data"
    work.mkdir(parents=True, exist_ok=True)
    templates = SCENARIO_IDS
    rows = []

    for v in range(n_variants):
        for template in templates:
            data = build_scenario(template, variant_seed=v + 1)
            d = work / f"{template}_v{v}"
            d.mkdir(parents=True, exist_ok=True)
            from cv2 import imwrite

            imwrite(str(d / "reference.png"), data["reference"])
            imwrite(str(d / "test.png"), data["test"])
            if data["view2"] is not None:
                imwrite(str(d / "view2.png"), data["view2"])

            gt = data["annotations"]
            base = baseline_run(d)
            images = {"reference": str(d / "reference.png"), "test": str(d / "test.png"),
                      "view2": str(d / "view2.png") if data["view2"] is not None else None}
            t0 = time.perf_counter()
            adaptive = asyncio.run(run_inspection(make_state(images, template, v, budget=12)))
            adapt_latency = round(time.perf_counter() - t0, 3)

            rows.append({
                "template": template,
                "variant": v,
                "gt_defects": len(gt),
                "baseline": {
                    **score_variant(gt, base["candidates"], verdict_level=True),
                    "detection": score_variant(gt, base["candidates"]),
                    "verdicts": verdict_counts(base["candidates"]),
                    "latency_s": base["latency_s"],
                    "tool_calls": 0,
                    "registration_quality": base["registration_quality"],
                },
                "adaptive": {
                    **score_variant(
                        gt,
                        [dict(c, bbox=c["bbox"]) for c in adaptive["candidates"].values()],
                        verdict_level=True,
                    ),
                    "detection": score_variant(
                        gt, [dict(c, bbox=c["bbox"]) for c in adaptive["candidates"].values()]
                    ),
                    "verdicts": verdict_counts(list(adaptive["candidates"].values())),
                    "latency_s": adapt_latency,
                    "tool_calls": adaptive["tool_calls_used"],
                    "registration_quality": (adaptive.get("registration") or {}).get("quality"),
                    "stop_reason": adaptive.get("stop_reason"),
                },
            })
            print(f"[{v + 1}/{n_variants}] {template}: "
                  f"base rep-F1={rows[-1]['baseline']['f1']:.2f} "
                  f"adapt rep-F1={rows[-1]['adaptive']['f1']:.2f} "
                  f"tools={adaptive['tool_calls_used']}")

    shutil.rmtree(work, ignore_errors=True)

    # aggregate
    agg: dict[str, dict] = {}
    for template in templates:
        tr = [r for r in rows if r["template"] == template]
        agg[template] = {
            "n": len(tr),
            "baseline": _mean_metrics(tr, "baseline"),
            "adaptive": _mean_metrics(tr, "adaptive"),
        }
    overall = {
        "n_inspections": len(rows),
        "baseline": _mean_metrics(rows, "baseline"),
        "adaptive": _mean_metrics(rows, "adaptive"),
    }
    result = {"synthetic_data": True, "iou_threshold": 0.15, "variants_per_template": n_variants,
              "overall": overall, "per_template": agg, "rows": rows}
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    write_markdown(result, out_dir / "results.md")
    return result


def _mean_metrics(rows: list[dict], which: str) -> dict:
    def m(key):
        vals = [r[which][key] for r in rows]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    total_v: dict[str, int] = {}
    for r in rows:
        for k, n in r[which]["verdicts"].items():
            total_v[k] = total_v.get(k, 0) + n
    return {
        "precision": m("precision"), "recall": m("recall"), "f1": m("f1"),
        "false_positives": sum(r[which]["fp"] for r in rows),
        "false_negatives": sum(r[which]["fn"] for r in rows),
        "mean_latency_s": m("latency_s"),
        "mean_tool_calls": m("tool_calls"),
        "escalation_rate": round(
            sum(total_v.get(k, 0) for k in ("NEEDS_REVIEW", "NOT_EVALUABLE"))
            / max(sum(total_v.values()), 1), 4),
        "verdicts": total_v,
        "registration_failures": sum(1 for r in rows if r[which]["registration_quality"] in ("poor", "failed")),
    }


def write_markdown(result: dict, path: Path) -> None:
    o = result["overall"]
    lines = [
        "# CircuitSleuth evaluation results",
        "",
        "> All data is **synthetic** (seeded generator, `tools/generate_dataset.py`).",
        "",
        f"{result['overall']['n_inspections']} inspections = {result['variants_per_template']} variants x 6 scenario templates.",
        "Headline precision/recall/F1 are **verdict-level**: only regions the system actually reports as a defect",
        f"(CONFIRMED/LIKELY) count as positives; cleared confounds are not alarms. Localization matching: IoU >= {result['iou_threshold']}.",
        "",
        "| Metric | Baseline (fixed pipeline) | CircuitSleuth (adaptive) |",
        "|---|---|---|",
        f"| Precision | {o['baseline']['precision']:.3f} | {o['adaptive']['precision']:.3f} |",
        f"| Recall | {o['baseline']['recall']:.3f} | {o['adaptive']['recall']:.3f} |",
        f"| F1 | {o['baseline']['f1']:.3f} | {o['adaptive']['f1']:.3f} |",
        f"| False positives | {o['baseline']['false_positives']} | {o['adaptive']['false_positives']} |",
        f"| False negatives | {o['baseline']['false_negatives']} | {o['adaptive']['false_negatives']} |",
        f"| Mean latency (s) | {o['baseline']['mean_latency_s']:.2f} | {o['adaptive']['mean_latency_s']:.2f} |",
        f"| Mean tool calls | {o['baseline']['mean_tool_calls']:.1f} | {o['adaptive']['mean_tool_calls']:.1f} |",
        f"| Escalation rate | {o['baseline']['escalation_rate']:.1%} | {o['adaptive']['escalation_rate']:.1%} |",
        f"| Registration failures caught | {o['baseline']['registration_failures']} | {o['adaptive']['registration_failures']} |",
        "",
        "## Per template",
        "",
        "| Template | n | Baseline P/R/F1 | Adaptive P/R/F1 | Adaptive tools/inspection |",
        "|---|---|---|---|---|",
    ]
    for template, a in result["per_template"].items():
        b, ad = a["baseline"], a["adaptive"]
        lines.append(
            f"| {template} | {a['n']} | {b['precision']:.2f}/{b['recall']:.2f}/{b['f1']:.2f} "
            f"| {ad['precision']:.2f}/{ad['recall']:.2f}/{ad['f1']:.2f} | {ad['mean_tool_calls']:.1f} |"
        )
    lines += [
        "",
        "## Interpretation notes",
        "",
        "- The baseline shares the same OpenCV core (registration + detection), so differences",
        "  come from *verification behavior*, not from a stronger detector.",
        "- Scenario 04 (mismatched capture) has no ground-truth defects: correct behavior is",
        "  refusing to report (NOT_EVALUABLE), reflected in registration failures caught.",
        "- Scenario 05 has no secondary view by design: the adaptive agent's correct behavior is",
        "  to request a new capture and escalate to human review instead of guessing, so its",
        "  reported-recall for this template is intentionally 0 while the baseline guesses.",
        "- Escalation rate includes deliberate, honest escalations — for the adaptive system",
        "  these replace fabricated confidence on ambiguous evidence.",
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=5)
    ap.add_argument("--out", type=Path, default=ROOT / "evaluation")
    args = ap.parse_args()
    result = run_benchmark(args.variants, args.out)
    o = result["overall"]
    print("\n=== OVERALL ===")
    print(f"baseline F1={o['baseline']['f1']:.3f}  adaptive F1={o['adaptive']['f1']:.3f}")
    print(f"baseline FP={o['baseline']['false_positives']}  adaptive FP={o['adaptive']['false_positives']}")
    print(f"adaptive mean tools={o['adaptive']['mean_tool_calls']:.1f}  latency={o['adaptive']['mean_latency_s']:.2f}s")


if __name__ == "__main__":
    main()
