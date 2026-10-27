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

## AWS execution

OpenCV 5.0.0 executed real inspections on EC2 t3.small in Stockholm, with
encrypted EBS, CloudWatch and private SSM access. The dated receipt identifies
commit `6281c2b`, Docker/source hashes, a passed HTTP smoke, six passed scenario
checks and 72 verified evidence hashes. See `docs/AWS_EXECUTION_2026-10-27.md`.
The final audit fixes postdate that AWS run and were validated separately.
No COOL or Graviton claim is made. A public judge endpoint remains to be provided.

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

Repository: https://github.com/sgoel2be24-cyber/circuitsleuth (public).

Python 3.13, Node 24; install `backend/requirements.lock.txt` and run frontend
`npm ci`. Follow `README.md`; run `scripts/verify_local.py --include-mcp` with
the virtual-environment Python. For Docker, follow `deploy/README.md`, then
`tools/http_smoke_test.py`. Six synthetic demos cover defects, clean boards,
glare, alignment failure, missing views and a constrained tool budget.

## Submission status

Pitch: `submission/PITCH.md`. Final team-selected video: https://youtu.be/ucM4NiEHInE.
It is unlisted and anonymously embeddable. The selected 2m03s file retains
recording-guide instructions and camera placeholders; the team explicitly
approved it as final after disclosure. Public synthetic app: https://decided-attributes-southwest-africa.trycloudflare.com.
It depends on the team Mac remaining online; this public route is separate
from the private AWS execution. Both Devpost team profiles are present.

Source upload command (portal limit 35 MB):
`python tools/package_submission.py --portal --out CircuitSleuth-Team-Update-portal.zip`.
This bundle retains runnable demos, source, tests and research results/provenance;
bulky research captures and video remain in the public repository. Final
rules/eligibility/rights confirmation and actual competition submission remain.
