# Devpost submission draft — CircuitSleuth

## Tagline

See deeper. Inspect smarter. Verify before deciding.

## The problem

Automated optical inspection pipelines run a fixed set of operations on a
fixed image. When a potential defect is ambiguous — glare, drift, small size,
noise, imperfect alignment — a fixed pipeline either floods operators with
false positives or quietly misses defects. It cannot *change its mind*, ask
for more evidence, or refuse to answer.

## Our solution

CircuitSleuth is an **active-perception inspection agent**. It aligns the test
board to a reference with OpenCV 5, detects candidate anomalies, measures its
own uncertainty, and then — per region — selects the cheapest tool that can
resolve that uncertainty: local re-registration (is it an alignment
artifact?), adaptive-threshold comparison (is it a glare confound?), an
independent captured view (does it reproduce?), edge topology or magnified
reprocessing (what geometry is it?). Findings are verified against accumulated
evidence; anything unresolved is escalated to human review with the full
evidence trail instead of guessed.

Everything the UI shows is real: the plan events, tool calls, artifact
thumbnails and metrics stream from the actual orchestrator via SSE.

## Why it's agentic (and provably so)

- The plan is never scripted per scenario: a documented priority score
  re-ranks (region, tool) pairs after every result (`backend/app/agent/policy.py`).
- Budget-bounded: when the tool budget runs out, unfinished regions are
  escalated — never invented.
- The same eight tools are exposed over a real MCP server (official SDK) so
  external clients can drive the same inspection; the orchestrator "merely"
  being a client of its own toolbelt is the point.

## Verification highlights

- Registration hardening: mutual matching + multiple RANSAC hypotheses
  verified photometrically + validated ECC refinement. This prevented a real,
  documented failure mode (periodic trace rows trapping RANSAC into a
  self-consistent 60 px-shifted warp).
- Honest refusal: on a mismatched board the system attempts recovery, then
  reports NOT_EVALUABLE with zero fabricated defects.
- Human review: when no second view exists, the agent formally requests a
  capture ("additional_capture_required") and escalates.

## Evaluation

30 seeded synthetic inspections (6 templates × 5 variants), fixed-pipeline
baseline vs adaptive agent on the same OpenCV core:

- Reported-F1: **0.571 → 0.716**
- Reported false positives: **52 → 10**
- Mean tool calls: 4.6 per inspection; mean latency ~1.4 s

Plus 37 automated tests, including end-to-end behavior assertions for all six
demo scenarios.

## Tech

Python 3.13 · FastAPI · OpenCV 5.0.0 (opencv-python-headless 5.0.0.93) ·
NumPy 2 · MCP SDK · SQLite · React 19 + TypeScript + Vite + Tailwind v4 ·
Docker-ready single container.

## AWS status (honest)

Local execution verified end-to-end. A single-container deployment
(Dockerfile + compose + App Runner instructions) is provided but the AWS run
itself is **unverified** — no AWS account was used for this submission.

## What's next

- S3-backed artifact storage + CloudWatch dashboards (deployment-day work).
- Optional LLM planner proposing tool arguments (schema-validated) alongside
  the deterministic baseline policy.
- Real multi-capture rig integration for genuine re-inspection loops.
