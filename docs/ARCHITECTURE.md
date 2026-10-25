# Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ React + TS + Vite + Tailwind (dark "mission control" UI)                 │
│  Dashboard · New inspection · Workspace (viewer + live feed + report)    │
└───────────────▲──────────────────────────────────┬───────────────────────┘
                │ SSE (real events)                │ REST / JSON
┌───────────────┴──────────────────────────────────▼───────────────────────┐
│ FastAPI (backend/app/api/routes.py)                                      │
│   /api/inspections…  ·  SSE /events  ·  artifacts  ·  operator review    │
├──────────────────────────────────────────────────────────────────────────┤
│ Agent orchestrator (backend/app/agent/orchestrator.py)                   │
│   OBSERVE → ALIGN → DETECT → (PLAN → ACT → VERIFY)* → DECIDE             │
│   policy.py: transparent priority score picks the next (region, tool)    │
├──────────────────────────────────────────────────────────────────────────┤
│ Toolbelt (backend/app/tools/registry.py) — same tools, two doors:        │
│   ① in-process orchestrator   ② MCP server (tools/mcp_server.py, stdio)  │
│   get_inspection_context · align_images · detect_defects ·               │
│   inspect_region · request_additional_view · verify_candidate ·          │
│   request_human_review · generate_inspection_report                      │
├──────────────────────────────────────────────────────────────────────────┤
│ OpenCV 5.0.0 pipeline (backend/app/cv/*)                                 │
│   preprocess → registration (SIFT/ORB mutual + RANSAC + photometric      │
│   hypothesis check + ECC) → detection (mean-transfer diff ⊗ local-NCC    │
│   mismatch ⊕ added-material channel, saturation mask) →                  │
│   region tools (zoom / edge / adaptive-threshold / local ECC /           │
│   independent view) → verification rule table → report                   │
├──────────────────────────────────────────────────────────────────────────┤
│ Persistence: SQLite index + per-run state.json + PNG artifacts           │
└──────────────────────────────────────────────────────────────────────────┘
```

## The agent loop

`orchestrator.run_inspection` drives a bounded loop. It never hardcodes a
scenario sequence: every `PLAN` step re-scores every open region with
`policy.priority_score` and executes the best action through the toolbelt.

Priority score (documented in `policy.py`):

```
score = 2.0·uncertainty + 1.5·severity + 0.8·(1−evidence_quality)
      + 1.2·info_gain − 0.6·tool_cost − 0.8·repeat_penalty + 1.0·closeout
```

Tool selection per region (`policy.choose_tool`) is an ordered hypothesis
test: misalignment (local ECC) → illumination confound (cheap adaptive
threshold) → independent view (or formal capture request) → edge topology →
high-res reprocessing → verify. Decisive evidence (view compared, alignment
artifact, proven confound) triggers immediate verification via a close-out
bonus so the budget is spent depth-first.

Stop conditions: all regions decided · tool budget exhausted · iteration
budget exhausted · unrecoverable registration failure. Exhausted regions are
escalated to human review, never guessed.

## Registration reliability

The core hardening that makes verdicts trustworthy (each documented in
`cv/registration.py`):

1. **Mutual + ratio matching** — one-directional matching on repetitive PCB
   textures admits self-consistent wrong warps.
2. **Multiple RANSAC hypotheses, verified photometrically** — inlier count
   alone prefers periodicity traps (a 60 px trace-row shift can gather huge
   false consensus). The winning hypothesis is the one that actually
   maximizes reference↔warped-test correlation.
3. **ECC refinement is validated** — ECC is only locally convergent and can
   slide to a periodic local optimum; the refined warp is accepted only if
   photometric agreement does not degrade.
4. **Quality gates** include coverage (share of the frame with inliers), so a
   partially-matched wrong board cannot pass as "good".

## Detection reliability

- Mean-transfer illumination normalization (σ=61) removes gain drift, shadows
  and glare while preserving absolute defect magnitudes.
- Local NCC mismatch is gated by reference structure (no structure → no
  mismatch evidence).
- An added-material channel catches copper on featureless background.
- Saturated pixels (glare clip knees) are excluded with a wide halo.
- All numeric outputs are named heuristic scores, never probabilities.

## Verdicts

`cv/verification.py` implements the explicit rule table (R1–R8) mapping
evidence to `CONFIRMED_DEFECT / LIKELY_DEFECT / CLEARED / NEEDS_REVIEW /
NOT_EVALUABLE`. Classification labels are hedged (`*_suspected`,
`unclassified_surface_anomaly`) with a recorded basis string.

## Persistence

SQLite (`data/circuitsleuth.db`) holds the inspection index and the full
event log. Each run directory holds `state.json` (the agent's complete
working state), input images and PNG artifacts — which is also what lets the
MCP server in a separate process resume any inspection by id.
