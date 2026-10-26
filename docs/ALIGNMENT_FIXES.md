# Alignment and evidence correctness fixes

Implemented 26 October 2026, following the isolated pipeline research.
This is the first production implementation phase; preprocessing redesign and
tiny-defect detection remain separate follow-up work.

## Result

The injected-defect probe that previously produced a false clearance now
retains supporting defect evidence. Conflicting local and independent-capture
evidence produces review. The existing adaptive benchmark retains reported
precision, recall and F1; this phase does not establish a general accuracy gain.

## Implementation

### ECC transform convention

The public registration convention remains **test → reference**. OpenCV ECC
uses **reference → test**: initial estimates are inverted before the call, and
results are inverted afterward, including coarse-to-fine scaling. The ordinary
forward-warp renderer, stored matrices, API coordinates and MCP rehydration
continue to use the existing public convention. Non-finite, singular and
reflected ECC updates are rejected. The original SIFT/ORB fallback order,
photometric acceptance checks and global thresholds are preserved.

### Local realignment

Both residuals now use 0–255 intensity units and the same commonly observed
candidate pixels. Motion is estimated from surrounding context, excluding the
candidate and a smoothing halo. Resampling uses ECC's inverse mapping and
propagates the valid-pixel mask. Candidate residuals are evaluated separately,
so an alignment fit cannot simply remove a real change from the fitting data.

Local comparison requires at least 64 textured context pixels, ECC correlation
≥0.7, positive determinant in [0.9, 1.1], maximum crop-corner displacement ≤6px,
and at least 8 common core pixels covering 90% of the candidate. Clearance
additionally requires >70% reduction, mean residual ≤4 intensity units and no
connected residual component of 3 or more pixels above a 12-unit difference.
These conservative heuristic gates are recorded, not calibrated probabilities.
They were not tuned to maximize the benchmark score.

Failures, blank context, excessive transforms, missing support and unexplained
residuals stay inconclusive. The tool keeps its existing name/evidence kind and
adds `measurement_version: local_ecc_v2`, intensity scale, support, reliability,
residual-component and transform metrics to the existing metrics dictionary.

### Evidence precedence and history

Local refutation cannot override a supporting second capture. Other explicit
local/capture conflicts also require review. An unreliable second capture
cannot be overridden by a same-capture clearance. Poor global registration
cannot be cleared by local reprocessing alone. An unreliable/inconclusive local
attempt cannot be used to justify an automatic same-capture verdict.

Older local evidence without a reliability marker is retained in history but
cannot clear a region when explicitly re-verified. Existing cached reports and
inspection files are not migrated or rewritten. IDs, API routes, schemas,
artifact naming, tool budgets and operator review/report paths are unchanged.

## Verification and measured effects

- **82 backend tests passed; 2 Windows-only tests skipped** on macOS. This
  includes 28 new cases covering forward/inverse conventions, initialized and
  pyramid ECC, invalid transforms, real defects with/without shifts, reliable
  pure shifts, masks, conflicts, failed fits and persistence/report serialization.
- Frontend lint and production build passed; all eight tools passed the actual
  MCP stdio smoke check. No frontend code changed in this implementation phase.
- Controlled global translation: interior pixel MAE **18.88 → 1.58**. This is
  an alignment diagnostic, not detection accuracy.
- The controlled real-defect local probe changes from `supports_defect: false`
  with an invalid 99.16% reduction claim to `true`, retaining the actual residual.
  Local before/after residuals now evaluate the core rather than the old padded
  window, so their absolute values are not directly comparable across versions.
- The original **30 synthetic inspections** were rerun into a separate output
  directory. Original results remain frozen. Adaptive macro precision **0.8627**,
  recall **0.7822**, F1 **0.7155**, FP **10** and FN **8** are unchanged. Candidate
  escalation increases **26.36% → 27.27%**. The fixed baseline has FP **52 → 50**,
  FN unchanged and macro F1 **0.5705 → 0.5751** after corrected registration.
- The actual persisted orchestrator ran before/after on the **48 research
  captures**, eight repeated synthetic board identities. Reported TP/FP/FN
  remain **87/22/33**, micro F1 **0.7598**, clean false positives **5**. This is a
  diagnostic regression set already examined in research, not a new test set.
- Four wrong-board controls show **no new acceptances**. Both versions still
  accept two mismatches and reject two: explicit board/revision identity remains
  an important unresolved weakness. The original wrong-board scenario also
  continues to pass its refusal regression test.
- Four fresh synthetic pose boards improve mean anchor error **0.0512 →
  0.0407px**, and worst error **0.0843 → 0.0539px**. Three cases improve; one
  changes from **0.0229 to 0.0539px**. No claim that every pose improves is made.

All data and original benchmark/research result JSONs are unchanged. Timing
numbers are machine-dependent; these checks do not establish AWS performance,
production accuracy or a statistical superiority claim.

## Reproduction and rollback

From the repository root, using installed locked dependencies:

```bash
.venv/bin/python scripts/verify_local.py --include-mcp
.venv/bin/python output/ecc-verification-fix/probes.py
.venv/bin/python output/ecc-verification-fix/compare_pipeline.py
CIRCUITSLEUTH_DATA_DIR=/tmp/circuitsleuth-ecc-benchmark .venv/bin/python evaluation/benchmark.py --variants 5 --out output/ecc-verification-fix/benchmark
```

The comparison command uses the existing local research captures and temporary
inspection storage. It does not edit the original research outputs. Evidence is
under `output/ecc-verification-fix/`: test logs, `correctness-probes.json`,
`comparison.json`, benchmark outputs and preservation manifests. The three
pre-fix production modules are retained under its `baseline/` directory, with
an incremental patch for review. Rollback should reverse only this phase's
changes, preserving the user's pre-existing uncommitted work and cached reports.

Historical research ablations now explicitly load three frozen baseline modules
under `research/pipeline-improvements/baseline/`. This preserves the meaning and
execution of their original source-based experiments after production changes.
The diagnostics parity check binds that same baseline for its historical check.
Original research datasets and result files remain unchanged.
