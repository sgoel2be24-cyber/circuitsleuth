# Evaluation

## Methodology

Reproducible benchmark: `evaluation/benchmark.py`.

- **Data**: seeded synthetic PCB generator (`tools/generate_dataset.py`), 6
  scenario templates × N variants (default 5) = 30 independent inspections.
  Every image, defect, illumination field and noise realization is derived
  from recorded seeds. **All data is synthetic** and clearly labeled as such;
  numbers describe this dataset, not production PCBs.
- **Baseline A (fixed inspection)**: the same OpenCV core — preprocess →
  register → detect — with rule verdicts computed from the detection scores
  alone. No secondary tools, no reprocessing.
- **CircuitSleuth (adaptive)**: the full active-perception agent over the
  identical core, with a 12-call tool budget.
- **Matching**: a candidate matches ground truth at IoU ≥ 0.15.
- **Headline metrics are verdict-level**: only regions reported as
  CONFIRMED/LIKELY count as positives — cleared confounds are not alarms.
  Raw detection-level metrics are also recorded in `results.json`.

## Current results after alignment/evidence fixes

The current 30-case run is in
`output/ecc-verification-fix/benchmark/results.json`: fixed/adaptive macro
precision 0.5208/0.8627, recall 0.8933/0.7822, F1 0.5751/0.7155, false positives
50/10, false negatives 6/8, candidate review rate 0%/27.27%. Macro averages
include the benchmark's empty/refusal-case conventions; F1 is not accuracy.
Lower reported false positives come with lower recall and human-review work.
See `docs/ALIGNMENT_FIXES.md` for additional controlled and research checks.

## Preserved original results (5 variants × 6 templates, OpenCV 5.0.0)

See `evaluation/results.md` / `results.json` for the generated tables. Summary:

| Metric | Baseline (fixed) | CircuitSleuth (adaptive) |
|---|---|---|
| Reported-F1 | 0.571 | **0.716** |
| Reported false positives | 52 | **10** |
| Mean tool calls | 0 | 4.6 |
| Mean latency | ~0.9 s | ~1.4 s |

Interpretation (also embedded in `results.md`):

- The detector is shared, so the gain comes from **verification behavior**,
  not a stronger detector: the agent clears illumination confounds, consults
  independent views, and refuses to report when registration fails.
- Scenario 04 (mismatched capture): correct behavior is refusing to report —
  both systems score "perfectly" only by NOT fabricating defects.
- Scenario 05 (no second view): the adaptive agent's correct behavior is to
  request a capture and escalate to human review, so its reported-recall is
  intentionally 0 while the baseline guesses.

## Operational metrics recorded per run

Tool calls, per-tool latency, escalation rate, registration quality, stop
reason — all persisted in the event log and visible in the UI report.

## Tests

Automated regressions cover registration (warp recovery, periodicity trap, wrong
board refusal), detection (ground-truth IoU, clean-board restraint), region
tools, the verification rule table, the planner, the orchestrator end-to-end
on all six scenarios, the REST API journey, and the MCP tool surface.

```bash
scripts\run_tests.bat      # or: cd backend && python -m pytest tests -q
```
