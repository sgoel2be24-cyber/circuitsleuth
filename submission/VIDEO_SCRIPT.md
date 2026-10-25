# Demo video script (3 minutes)

Recording setup: `scripts\run_dev.bat`, full-screen browser at 1440×900,
dashboard pre-seeded with a few completed runs. Everything shown runs live.

| Time | Shot | Talk track |
|---|---|---|
| 0:00–0:15 | Dashboard | "Fixed AOI pipelines can't change their minds. CircuitSleuth is an agent that measures its own uncertainty and decides what to look at next. Everything you'll see is live." |
| 0:15–0:40 | New inspection → scenario 3 (glare) | "A pinhole defect captured under strong glare. Watch the plan events — the agent picks every next tool from measurements." |
| 0:40–1:30 | Workspace, live feed | "It aligns with SIFT, detects a suspicious region — flagged illumination-suspect. First it runs the *cheap* confound test: adaptive thresholding. The glare ghosts get cleared in one call each. The real defect survives, so it consults an independent captured view — that's genuinely new optical evidence — and confirms." (hover the artifact thumbnails) |
| 1:30–2:00 | Region detail + Report | "Every claim has an evidence trail: which tool, what it measured, whether it supports or refutes, and whether it reprocessed pixels or fetched a new view. The report exports as JSON with limitations attached." |
| 2:00–2:30 | Scenario 5 (no second view) | "Here no second capture exists. The agent formally requests one, receives 'capture required', and escalates to a human review — I confirm it, and the audit trail records the human decision." Then scenario 4: "Mismatched board: registration refuses after recovery — NOT_EVALUABLE, zero fabricated defects." |
| 2:30–3:00 | Benchmark + MCP | "On 30 seeded inspections, verification behavior cuts reported false positives from 56 to 13 and lifts F1 from 0.57 to 0.72 — same OpenCV core, agentic verification only. And the same eight tools are exposed over MCP, so any client can drive the same inspection." |

Recording tips:
- Use the workspace's SSE feed as the visual anchor; call out PLAN/ACT/VERIFY chips.
- Zoom into the board viewer on R01 before opening Region detail.
- Keep the benchmark table (`evaluation/results.md`) open in an editor tab.
