# Demo scenarios

All demo data is **synthetic**, rendered by the seeded generator in
`tools/generate_dataset.py` (2× supersampled boards, copper traces, pads,
silk, procedural illumination/noise/glare). Regenerate with:

```bash
.venv\Scripts\python.exe tools\generate_dataset.py --force
```

Each scenario directory (`data/demo/<id>/`) contains `reference.png`,
`test.png`, optional `view2.png` (an independently rendered capture of the
same physical board — genuinely new optical evidence, not a crop),
`annotations.json` (ground truth, used only for evaluation — never shown to
the agent) and `meta.json` (provenance).

| # | Scenario | What it demonstrates |
|---|---|---|
| 1 | Clearly defective board | 3 gross defects, good imaging → registration good, agent verifies and confirms with evidence |
| 2 | Clean board | no anomalies → the system must **not** manufacture defects |
| 3 | Ambiguous glare | pinhole under specular glare → agent tests the illumination confound cheaply, consults the independent view, confirms the real defect, clears the ghosts |
| 4 | Registration failure | test image is a different board revision → alignment refused after recovery attempt → NOT_EVALUABLE, zero fabricated defects |
| 5 | No second view | moderate defect under glare, single capture → agent formally requests a new view, receives "capture required", escalates to human review |
| 6 | Multiple regions | 5 defects of mixed severity → priority-ordered verification, tool budget respected, independent per-region states |

The six behaviors map one-to-one to the spec's required demonstrations and are
asserted by the automated test suite (`backend/tests/test_orchestrator.py`).

## Suggested demo walkthrough (for the video)

1. Dashboard → 2. New inspection → pick **scenario 3** → watch the live feed
(PLAN/ACT events with artifact thumbnails) → open **Region detail** (evidence
trail, confound badge) → **Report** tab → download JSON.
3. Run **scenario 5** → operator decision panel → Confirm → audit trail updates.
4. Run **scenario 4** → show the honest refusal (registration_failed).
5. Show `evaluation/results.md` and the MCP config.
