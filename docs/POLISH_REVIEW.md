# CircuitSleuth polish and reevaluation

This records the initial polish snapshot. Subsequent production alignment and
evidence fixes are documented in [ALIGNMENT_FIXES.md](ALIGNMENT_FIXES.md).

Reviewed by Codex on 26 October 2026 against the supplied ZIP and live
[OpenCV competition requirements](https://opencv26.devpost.com/).

## Verdict

Preserve the existing inspection pipeline. Its substantive OpenCV 5 processing,
evidence-driven tool selection, independent-view checks, explicit uncertainty,
and human escalation form a coherent Agentic Vision demonstration. The local
implementation is working; submission readiness still depends on actual AWS
execution and judge-accessible deliverables.

## Changes

- Removed the unused import that caused the fresh production build to fail
  with TypeScript TS6133.
- Added **Show more inspections** to the ledger. Previously only the first nine
  loaded rows could be browsed; changing a search or filter resets the window.
  The existing API still returns its latest 100 inspections.
- Scoped the ledger's absolute screen-reader label to its scroll container,
  fixing page-wide horizontal overflow at a 390 px phone viewport. The table
  retains its own horizontal scrolling.
- Added **Re-run inspection** for terminal runs. It invokes the existing clone
  endpoint, produces a new ID and audit trail, and preserves the original report.
  This also provides a retry path if capture upload succeeds but rerunning fails.
- Disabled operator decisions until the inspection is completed, matching the
  API's existing rule; failed runs can be rerun to finish verification.
- Added a portable verifier and macOS/Linux setup instructions using the existing
  lock files. Removed the Windows verifier's obsolete HTTP-server prerequisite
  for the independent MCP stdio smoke test. Its `ApiBase` parameter remains
  accepted for compatibility.

The backend, CV algorithms, policy, schema, dependency locks, demo files,
original benchmark results, API paths, candidate IDs, and artifact naming are
unchanged byte-for-byte from the supplied archive. The route's existing
`key={pathname}` already isolates workspace state across runs; it was retained.

## Verification

| Check | Evidence |
|---|---|
| Original backend baseline | 54 passed, 2 Windows-only tests skipped |
| Final local verifier | Dependency consistency, OpenCV 5.0.0, 54 passed / 2 skipped, frontend lint and build, MCP smoke |
| MCP stdio | All eight tools executed; 10 consecutive persisted audit events |
| Benchmark | 30 inspections; every non-timing JSON output equals the supplied results |
| Integrity | SHA-256 comparison to original ZIP; all backend, dataset and evaluation files preserved |
| Browser | Operator review, report download, fresh rerun and original-report preservation; ledger browsing and responsive checks recorded in `output/playwright/` |

Evidence: `output/verification/local-checks.log`, `frontend-build.log`,
`benchmark.log`, `benchmark-comparison.json`, `archive-integrity.json` and
`output/playwright/`. Browser and benchmark runs used separate temporary data
directories, leaving bundled historical inspections untouched.

## Results and practical limits

| Macro metric across 30 synthetic inspections | Fixed baseline | Adaptive agent |
|---|---:|---:|
| Reported precision | 0.516 | 0.863 |
| Reported recall | 0.893 | 0.782 |
| Reported F1 | 0.571 | 0.716 |
| Reported false positives | 52 | 10 |
| False negatives | 6 | 8 |
| Escalation rate | 0% | 26.4% |

The reduction in false alarms trades some reported recall for escalation.
These are synthetic, low-IoU (0.15) localization measurements, averaged per
inspection. Registration refusals with no annotated defects also contribute
perfect empty-case scores; the headline is not a production PCB accuracy
estimate. Runtime timings depend on the machine. Original results are preserved;
this machine's rerun is under `output/verification/benchmark/`.

## Competition readiness

| Criterion | Weight | Assessment |
|---|---:|---|
| Technical execution | 30% | OpenCV 5 runtime and existing regressions verified |
| Innovation | 20% | Visual measurements change later tool calls and escalation; retain the explicit planner |
| Real-world impact | 20% | Useful inspection problem, but synthetic evidence only; no production validation |
| User experience | 10% | Working inspection, evidence, report and review flow; targeted navigation fixes |
| Documentation/presentation | 10% | Reproduction and technical report provided; actual team/demo video still needed |
| Cloud/reproducibility/responsible operation | 10% | Locks verified locally; AWS workload and container execution remain unverified |

Source: [judging criteria and requirements](https://opencv26.devpost.com/).
No numerical judge score is inferred from this review.

Before submitting, provide evidence of a meaningful AWS inspection, a
judge-accessible repository/archive, an endpoint or arranged screen-share,
and a public/unlisted video of at most five minutes showing the team, working
application, architecture and results. The tool-reported deliverables also flag
an archive as required. No COOL execution was found; a COOL award claim needs
additional Arm/Graviton execution and comparison evidence.

The site's prose/announcement says 26 October 11:59 p.m. Pacific
(27 October 12:29 p.m. IST), but its structured submission deadline is
27 October 06:45 UTC (12:15 p.m. IST). Use the earlier **12:15 p.m. IST on
27 October** as the conservative cutoff; confirm the actual Devpost countdown.
No project was submitted or cloud service deployed during this review.
