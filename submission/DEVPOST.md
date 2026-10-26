# Devpost submission draft — CircuitSleuth

**Team Update — Shikhar Goel and Ishpreet Singh**

## Tagline

See deeper. Inspect smarter. Verify before deciding.

## Inspiration and problem

A suspicious mark on a PCB can be a defect, glare or alignment error. Inspection
operators need an evidence trail and a useful next step when the first image is
inconclusive. CircuitSleuth investigates candidate changes with OpenCV 5,
selects follow-up tools from the measurements, and escalates unresolved cases.

## What it does

The operator supplies a reference and test board. OpenCV 5 performs alignment,
change detection, local registration, illumination-confound analysis and
independent-view comparison. A deterministic planning policy ranks open regions
using uncertainty, severity, evidence quality, information gain and tool cost.
Measurements and existing evidence change the next tool selection.

The UI streams actual PLAN/ACT/VERIFY events, image artifacts and final verdicts.
Operators can review a region, record a decision, supply another capture and
start a fresh run while preserving the original audit trail. Missing views
produce capture requests; failed alignment can produce a refusal to evaluate.
The same eight tools are accessible through MCP.

## How we built and checked it

Python 3.13, FastAPI, OpenCV 5.0.0, NumPy 2, MCP SDK, SQLite, React 19,
TypeScript, Vite, Tailwind 4 and a single Docker container. Dependency locks,
a portable verifier and Linux CI cover backend, frontend, MCP and an actual
container HTTP inspection. The evidence exporter exercises all six demo cases
and saves reports, raw events, planning references, PNGs and file hashes.

Correctness work repaired ECC warp direction, validated local alignment evidence
and sent conflicting views to human review. This avoids clearing a real defect
just because unconstrained re-alignment makes the image difference look smaller.

## Results

Current code, 30 seeded synthetic inspections (6 templates × 5 variants), fixed
single-pass versus adaptive verification using the same current OpenCV core:

| Metric | Fixed | Adaptive |
|---|---:|---:|
| Macro reported precision | 0.5208 | 0.8627 |
| Macro reported recall | 0.8933 | 0.7822 |
| Macro reported F1 | 0.5751 | 0.7155 |
| Reported false positives | 50 | 10 |
| Candidate verdicts requiring review | 0% | 27.27% |

The 80% reduction in reported false positives has a recall/review trade-off.
These metrics describe seeded synthetic images at IoU 0.15, not production
accuracy. The limited external research check showed a substantial domain gap;
wrong-board identity checks and small-defect sensitivity remain open work.

## AWS status — replace only after an actual evidenced run

The EC2/SSM/CloudWatch deployment template is prepared. It runs the same Docker
container with encrypted local EBS storage, no inbound application access and
an authenticated Session Manager demonstration. AWS execution is **pending**
service checks and the actual deployment. Container
CI is not AWS proof. The older App Runner template is for existing customers
only; App Runner is closed to new customers.

## Intended award consideration

Agentic Vision: OpenCV measurements change subsequent tool calls, verification
and human-review actions. See the workflow in `docs/TECHNICAL_REPORT.md` and the
raw evidence in `output/submission-readiness/demo-evidence/`. No COOL award
claim: COOL on AWS Graviton has not been implemented or evaluated.

## Responsible use and next steps

Use as a supervised demonstration. Scores are heuristics, not probabilities;
there is no production PCB validation or automatic capture rig. The private
AWS route avoids exposing the unauthenticated upload/review API. Planned future
work includes real manufacturing data, stronger board identity and durable
multi-instance storage.

## Repository and testing instructions

Repository: https://github.com/sgoel2be24-cyber/circuitsleuth (private; judge
access must be arranged, or provide the source ZIP).

Python 3.13, Node 24; install `backend/requirements.lock.txt` and run frontend
`npm ci`. Follow `README.md`; run `scripts/verify_local.py --include-mcp` with
the virtual-environment Python. For Docker, follow `deploy/README.md`, then
`tools/http_smoke_test.py`. Six synthetic demos cover defects, clean boards,
glare, alignment failure, missing views and a constrained tool budget.

## Submission status

Pitch prepared in `submission/PITCH.md`. Video production deferred by the team;
a judge-accessible video of at most five minutes remains required. AWS proof,
judge access/live demonstration arrangement, final eligibility/rights review
and actual Devpost submission remain pending. This file is a draft.
