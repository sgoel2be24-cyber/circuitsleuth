"""Stage 6 — verification: combine evidence into a final verdict.

Explicit rule table, evaluated in order. First matching rule wins. The table is
deliberately simple and inspectable — judges can trace every verdict.

  R1  registration poor/failed and never recovered          -> NOT_EVALUABLE
  R2  candidate touches the warp-invalid border and no
      independent view resolved it                          -> NOT_EVALUABLE
  R3  conflicting local/independent evidence               -> NEEDS_REVIEW
  R4  an independent view was compared:
        - anomaly persists + strong baseline                -> CONFIRMED_DEFECT
        - anomaly persists                                  -> LIKELY_DEFECT
        - anomaly absent, comparison reliable               -> CLEARED (observation artifact)
        - unreliable comparison                             -> NEEDS_REVIEW
      otherwise a reliable local realignment may clear;
      unqualified/inconclusive local evidence              -> NEEDS_REVIEW
  R5  strong baseline + >=2 reprocessing tools agree        -> CONFIRMED_DEFECT
  R6  moderate baseline + >=1 tool agrees                   -> LIKELY_DEFECT
  R7  illumination confound with no structural support      -> CLEARED
  R8  otherwise                                             -> NEEDS_REVIEW

"Strong baseline" = difference_score >= 0.15 AND structural_mismatch >= 0.32.
"Moderate" = difference_score >= 0.08 OR structural_mismatch >= 0.30.
Classification (label) is separate from verdict and may honestly be
"unclassified_surface_anomaly".
"""

from __future__ import annotations

from typing import Any

STRONG_DIFF = 0.15
STRONG_MISMATCH = 0.32
MODERATE_DIFF = 0.08
MODERATE_MISMATCH = 0.30


def _supports(evidence: list[dict], kinds: set[str]) -> list[dict]:
    """Supporting evidence, deduplicated by source tool (one vote per tool)."""
    out: dict[str, dict] = {}
    for e in evidence:
        if e.get("evidence_kind") in kinds and e.get("supports_defect") is True:
            out[e.get("source_tool", "?")] = e
    return list(out.values())


def _refutes(evidence: list[dict], kinds: set[str]) -> list[dict]:
    out: dict[str, dict] = {}
    for e in evidence:
        if e.get("evidence_kind") in kinds and e.get("supports_defect") is False:
            out[e.get("source_tool", "?")] = e
    return list(out.values())


def verify_candidate(
    cand: dict[str, Any],
    evidence: list[dict],
    registration_quality: str,
) -> tuple[str, str | None, str, list[str]]:
    """Return (verdict, label, label_basis, notes)."""
    diff = float(cand.get("difference_score", 0.0))
    mismatch = float(cand.get("structural_mismatch_score", 0.0))
    quality = float(cand.get("evidence_quality_score", 0.0))
    notes: list[str] = []

    strong = diff >= STRONG_DIFF and mismatch >= STRONG_MISMATCH
    moderate = diff >= MODERATE_DIFF or mismatch >= MODERATE_MISMATCH

    local_evidence = [e for e in evidence if e.get("evidence_kind") == "local_realignment"]
    # Older persisted evidence has neither consistent units nor a support
    # quality gate. Retain its audit record, but do not trust it to clear.
    qualified_local = [e for e in local_evidence
                       if (e.get("metrics") or {}).get("comparison_reliable") is True]
    realign_support = _supports(qualified_local, {"local_realignment"})
    realign_refute = _refutes(qualified_local, {"local_realignment"})
    view_support = _supports(evidence, {"independent_view"})
    view_refute = _refutes(evidence, {"independent_view"})
    reprocess_support = _supports(evidence, {"difference_severity", "edge_topology", "illumination_confound"})
    reprocess_refute = _refutes(evidence, {"difference_severity", "edge_topology", "illumination_confound"})

    # R1 — handled by caller for registration-level failure; still guard here.
    if registration_quality in ("poor", "failed") and not view_support:
        return "NOT_EVALUABLE", None, "registration unreliable", [
            "Registration quality was %s; refusing to report defects without independent confirmation." % registration_quality
        ]

    # R2 — touches warp-invalid border
    if cand.get("touches_invalid_warp_region") and not view_support:
        return "NOT_EVALUABLE", None, "candidate lies at the aligned-image border", [
            "Candidate touches the region where warped test pixels are missing; evidence incomplete."
        ]

    # R3 — no single source overrides an explicit evidence conflict.
    if ((view_support and _refutes(local_evidence, {"local_realignment"}))
            or (view_refute and realign_support) or (view_support and view_refute)
            or (realign_support and realign_refute)):
        return "NEEDS_REVIEW", *_classify(cand, evidence), [
            "Conflicting evidence from local realignment or independent captures; operator review required."
        ]

    # R4 — independent view was actually compared
    if any(e.get("evidence_kind") == "independent_view" for e in evidence):
        if view_support and strong and quality >= 0.4:
            return "CONFIRMED_DEFECT", *_classify(cand, evidence), []
        if view_support:
            return "LIKELY_DEFECT", *_classify(cand, evidence), []
        if view_refute:
            if strong or moderate:
                # baseline says defect, independent view disagrees: honest conflict
                return "NEEDS_REVIEW", *_classify(cand, evidence), [
                    "Conflicting evidence: baseline difference is present but the anomaly did not reproduce in the independent view."
                ]
            return "CLEARED", None, "not present in independent view", [
                "The anomaly did not reproduce in an independent capture; likely an observation artifact."
            ]
        return "NEEDS_REVIEW", *_classify(cand, evidence), [
            "Independent view comparison was unreliable; additional reprocessing cannot resolve this evidence gap."
        ]

    if local_evidence and (len(qualified_local) != len(local_evidence)
                           or any(e.get("supports_defect") is None for e in local_evidence)):
        return "NEEDS_REVIEW", *_classify(cand, evidence), [
            "Local alignment evidence was unreliable or inconclusive; it cannot justify an automatic verdict."
        ]

    if realign_refute:
        m = realign_refute[-1].get("metrics", {})
        return "CLEARED", None, "registration artifact", [
            "Reliable local ECC removed %s of the local difference on common observed pixels, with no coherent residual."
            % m.get("reduction_ratio", "?")
        ]
    # R5/R6/R7 — reprocessing evidence only
    if strong and quality >= 0.35 and len(reprocess_support) >= 2 and not reprocess_refute:
        verdict = "CONFIRMED_DEFECT"
        label, basis = _classify(cand, evidence)
        notes.append("Strong difference + structural mismatch confirmed by %d reprocessing tools (no independent view available)." % len(reprocess_support))
        return verdict, label, basis, notes
    if moderate and (reprocess_support or realign_support) and not reprocess_refute:
        label, basis = _classify(cand, evidence)
        return "LIKELY_DEFECT", label, basis, ["Moderate baseline evidence with at least one supporting secondary analysis."]
    confound_proven = any(
        e.get("source_tool") == "adaptive_threshold"
        and (e.get("metrics") or {}).get("illumination_confound_likely")
        for e in evidence
    )
    if (cand.get("illumination_suspect") or confound_proven) and not reprocess_support and not realign_support:
        return "CLEARED", None, "illumination confound", [
            "Difference is high but structural mismatch is low and adaptive-threshold analysis found no geometry change — consistent with glare/shadow."
        ]
    if moderate:
        label, basis = _classify(cand, evidence)
        return "NEEDS_REVIEW", label, basis, ["Evidence inconclusive after available analyses; escalating to human review."]
    label, basis = _classify(cand, evidence)
    return "NEEDS_REVIEW", label, basis, ["Baseline evidence too weak to classify; escalating to human review."]


def _classify(cand: dict[str, Any], evidence: list[dict]) -> tuple[str, str]:
    """Geometry-informed, explicitly hedged defect classification.

    Polarity comes from edge_topology evidence when available, otherwise from
    detection-time measurements (edge_delta / added_on_flat_background).
    Returns (label, basis). Honest fallback: 'unclassified_surface_anomaly'.
    """
    edge_ev = [e for e in evidence if e.get("evidence_kind") == "edge_topology"]
    area = int(cand.get("area_px", 0))
    diff = float(cand.get("difference_score", 0.0))

    polarity = edge_ev[-1]["metrics"].get("polarity") if edge_ev else None
    polarity_basis = "edge topology analysis"
    if polarity is None:
        if cand.get("added_on_flat_background"):
            polarity = "material_added"
            polarity_basis = "detection: added copper on featureless background"
        elif float(cand.get("edge_delta", 0.0)) < -0.3:
            polarity = "material_removed"
            polarity_basis = "detection: reference edges missing in test"
        elif float(cand.get("edge_delta", 0.0)) > 0.3:
            polarity = "material_added"
            polarity_basis = "detection: new edges present in test"

    if polarity == "material_removed":
        if area <= 260:
            return "pinhole_or_mousebite_suspected", "small removal per " + polarity_basis
        return "open_circuit_suspected", "large material removal per " + polarity_basis
    if polarity == "material_added":
        if area <= 200:
            return "spur_or_spurious_copper_suspected", "small added copper per " + polarity_basis
        return "short_or_spurious_copper_suspected", "added copper per " + polarity_basis
    if diff >= STRONG_DIFF:
        return "unclassified_surface_anomaly", "strong difference but polarity analysis inconclusive"
    return "unclassified_surface_anomaly", "insufficient evidence for class assignment"
