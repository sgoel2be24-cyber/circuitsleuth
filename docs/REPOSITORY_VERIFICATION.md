# Repository verification

26 October 2026. Scope: the complete CircuitSleuth project, research, synthetic
capture fixtures, documentation and recorded verification evidence.

## Local checks before publication

- Locked dependency consistency and OpenCV 5 runtime passed.
- Backend: 100 passed, two Windows-only filesystem tests skipped on macOS.
- Frontend: lint and production build passed.
- MCP: all eight tools executed over actual stdio; audit sequences preserved.
- Controlled alignment and evidence probes passed.
- The actual orchestrator was cross-checked again on 48 research captures before
  and after the fixes: TP/FP/FN 87/22/33 in both versions, with no new wrong-board
  acceptance in the four mismatch controls. Existing board-identity weaknesses
  remain documented in `ALIGNMENT_FIXES.md`.
- Original synthetic benchmark results and research result archives are retained;
  implementation evaluations use their own output directory.
- Upload candidates were inspected for high-confidence credential patterns.
  Environment files, dependencies and generated runtime databases are excluded.

The original source remote is retained as `source-origin`; the new `origin`
points to the signed-in user's private repository. Original Git history is
preserved. Runtime files and local source archives remain available locally.

## Repeatable clean-checkout verification

`.github/workflows/verify.yml` pins official checkout/setup actions to exact
commits and installs the existing Python/frontend lock files on Linux. It runs
`scripts/verify_local.py --include-mcp`, builds `deploy/Dockerfile`, starts the
image and exercises `tools/http_smoke_test.py` against it. The HTTP readiness check tolerates transient connection resets while Docker
starts the application, with a bounded wait and no retries of mutation calls.
Six regressions cover startup transport failures, timeout and incompatible
OpenCV versions. The HTTP check covers
OpenCV 5 health, the frontend deep link, six demo scenarios, real adaptive
inspection, its report/events and all three candidate crop endpoints.

The Actions result on the published commit is the authoritative record for the
Linux/container run. The local Docker daemon was unavailable, so no local
container execution is claimed. No AWS resources or Devpost submission are
created by this workflow.

Evidence from the final local cross-check is in `output/final-crosscheck/`;
implementation and research comparisons remain in their existing directories.

To run against disposable local storage:

```bash
.venv/bin/python scripts/verify_local.py --include-mcp
# With the application already running against a disposable data directory:
.venv/bin/python tools/http_smoke_test.py --base-url http://127.0.0.1:8100
```

The HTTP check creates a synthetic inspection and preserves its audit trail.
Historical research ablations use the frozen modules under
`research/pipeline-improvements/baseline/`. Their captures/results are included
for reproducibility; regeneration commands and third-party dataset provenance
are recorded in the research report.

## Competition-readiness additions — 26 October

Team Update credits and a pitch were prepared; video production was deferred
by the user. Submission claims now use the corrected 30-case benchmark rather
than mixing historical baseline counts. The official requirements snapshot and
readiness matrix expose the remaining AWS/video/judge-delivery requirements.

The six-scenario HTTP exporter saves actual reports, complete events, PNGs and
hashes. The source packager excludes secrets/runtime files and third-party
DeepPCB captures, with twelve regressions protecting those boundaries. The AWS
EC2/SSM template is statically checked with cfn-lint; no AWS run is claimed.
The container CI now exercises the six-case evidence exporter as well.
