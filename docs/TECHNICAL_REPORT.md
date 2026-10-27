# CircuitSleuth technical report

27 October 2026 · Team **Update** · **Shikhar Goel and Ishpreet Singh**

## Problem and users

PCB inspection operators need to separate actual surface changes from glare,
misalignment and image noise. CircuitSleuth compares a reference and test board,
then investigates uncertain regions. The current product is a supervised
synthetic demonstration for inspection engineers and evaluators, with support
for uploaded images. Manufacturing accuracy and time savings are not established.

## Implemented architecture and agent workflow

```mermaid
flowchart TD
    UI[React UI: configure, inspect, review, export] --> API[FastAPI REST and SSE]
    API --> Perception[OpenCV 5 alignment and change detection]
    Perception --> Plan[Rank open regions and follow-up tools]
    Plan --> Act[Local ECC, thresholding, topology or separate view]
    Act --> Evidence[Accumulate metrics and image artifacts]
    Evidence --> Plan
    Evidence --> Verify[Explicit verification rules]
    Verify --> Decision[Confirm, clear, review or not evaluable]
    Decision --> UI
    Plan --> Budget[Budget and iteration stop conditions]
    Budget --> Human[Capture request or human review]
    Human --> UI
    MCP[External MCP clients] --> Tools[Same eight inspection tools]
    Tools --> Perception
    API --> Store[SQLite, JSON state and PNG evidence]
    Evidence --> Store
```

The deterministic policy is in `backend/app/agent/policy.py`: current uncertainty,
severity, quality, estimated information gain, cost and repeat penalties rank
candidate/action pairs. Measured illumination and alignment flags affect which
tool runs; decisive accumulated evidence changes the next action to verification.
The policy is transparent and budget-bounded, without an LLM dependency.
Raw `plan_selected` and tool events show the actual executed sequence. The
exported planning reference list points to preceding observation events; those
references are an audit aid, not an independent causal experiment.

OpenCV 5.0.0 performs substantive analysis: SIFT/ORB feature matching, RANSAC
registration hypotheses, photometric verification and ECC refinement; normalized
image differences and local structural comparisons; topology, thresholding,
local registration and independent-view analysis. Scores are heuristics, not
calibrated probabilities. MCP calls and the web orchestrator share tools.

Recent correctness fixes repair ECC transform direction, exclude candidate
pixels from the local registration fit, compare common valid support and
require reliable local evidence before clearing a candidate. Conflicting local
and second-view evidence is escalated. Controlled probes expose the previous
false-clear failure. Details and remaining risks: [alignment fixes](ALIGNMENT_FIXES.md).

## AWS architecture — executed in Stockholm

```mermaid
flowchart LR
    Source[Private S3 source ZIP plus SHA256] --> Host[EC2 t3.small in eu-north-1]
    Operator[Authenticated operator] -->|SSM tunnel, no inbound ports| Host
    Host -->|Docker| Runtime[FastAPI, React and OpenCV 5]
    Runtime --> EBS[Encrypted EBS: SQLite, JSON and PNG]
    Runtime --> CW[CloudWatch logs]
    Host --> Proof[Private S3 evidence archive]
    Operator -. public endpoint or screen-share still needed .-> Judges[Judges]
```

The AWS run at application commit `6281c2be7d3832b26b3522202a5f5fea59af1825`
passed a real HTTP inspection, all six demo behavior checks and verification of
72 evidence hashes. OpenCV 5.0.0 executed the vision workload on EC2; the receipt
records the container image and source-archive digest. See [dated AWS execution
record](AWS_EXECUTION_2026-10-27.md) and [sanitized receipt](../submission/evidence/aws-verification-redacted.json).
The complete hosting evidence is retained privately by the team.

The final lifecycle/capture/glare/review/UI fixes were validated locally after
that AWS run. The existing AWS receipt does not attest to these later changes;
any deployment of the final release should record its new manifest commit.

`deploy/aws-ec2-demo.template.json` checks the source ZIP SHA256, builds on the
host, binds the application to loopback and schedules a stop six hours after
first boot. Standard T3 CPU credits avoid surplus CPU charges. Encrypted EBS
persists through container restarts and instance stop/start; stopping does not
remove storage/log charges. The approved run used Free Plan credits only, with
a USD 1 credit budget and no paid upgrade. Actual final billing is not established.

The IAM role scopes source reads, evidence writes, logs and SSM operations.
The security group has no inbound rules. Private SSM access is not a public
judge endpoint. A public endpoint or explicitly arranged live screen-share is
still required. The scheduled stop is not proof of current instance state.
This is a single-instance demo without backups or shared storage.
No COOL/Graviton execution or performance comparison is claimed.

## Reproduction and verification

Use Python 3.13 and Node 24, install the backend lock and frontend `npm ci`.
Run `scripts/verify_local.py --include-mcp` using the virtual-environment Python.
The final local suite and targeted packaging check passed; exact counts and commands are
recorded in [final check](FINAL_CHECK_2026-10-27.md). Two Windows-specific tests are skipped on macOS;
frontend lint/build and all eight MCP tools passed. The earlier published
Linux CI also verified a real Docker build and HTTP inspection. The current
commit's Actions result is authoritative for its container checks.

`tools/export_demo_evidence.py` executes all six API demos with behavior checks,
saving reports, complete events, planning references, PNG crops and SHA256s.
Run it with `python -m tools.export_demo_evidence --out NEW_DIRECTORY` against
a disposable running API. Default URL is localhost:8080. An AWS claim additionally
requires AWS identity/instance/command evidence tied to the exported inspection
IDs; neither an environment variable nor the exporter certifies cloud hosting.

Source packages use `tools/package_submission.py`; source commit and file hashes
are embedded. DeepPCB third-party images, credentials and runtime data are
excluded. Synthetic fixtures, source, dependency locks and recorded findings
remain in the judge package. See [deployment](../deploy/README.md) and
[repository verification](REPOSITORY_VERIFICATION.md).

## Evaluation and trade-offs

Current code: 30 seeded synthetic inspections (six templates, five variants),
fixed versus adaptive on the same OpenCV core. Ground-truth matching uses IoU
0.15; reported positives are confirmed/likely verdicts. Headline precision,
recall and F1 are per-inspection macro averages, including the benchmark's
empty/refusal-case conventions. They are not binary accuracy percentages.

| Metric | Fixed | Adaptive |
|---|---:|---:|
| Macro reported precision | 0.5208 | 0.8627 |
| Macro reported recall | 0.8933 | 0.7822 |
| Macro reported F1 | 0.5751 | 0.7155 |
| False positives | 50 | 10 |
| False negatives | 6 | 8 |
| Candidate review rate | 0% | 27.27% |

The 80% reported-FP reduction has lower recall and added review workload. The
current results live in `output/final-check-2026-10-27/benchmark.json`;
the original `evaluation/results.json` remains preserved (52 original baseline
FP). Timing is machine-specific; no cloud latency or cost measurement exists.

The 48-capture research comparison retained TP/FP/FN 87/22/33 before and after
the correctness fixes. Two of four research mismatch controls were wrongly
accepted by both versions; no new acceptances were introduced. A six-pair
external DeepPCB smoke check matched only one of thirty annotated defects,
showing substantial domain gap. These checks do not establish production
readiness. Research preprocessing ablations were not promoted wholesale:
unsafe registration fallback could accept a wrong board, and CLAHE could
increase false positives. See the retained research report and source evidence.

## Limitations and responsible operation

Core benchmark imagery and second views are separately rendered synthetic
captures; no physical camera rig is integrated. Reprocessing the same image
adds no optical information. The demonstration may miss small defects,
mishandle board identity or require more review under new imaging conditions.
Confidence is uncalibrated. Uploaded-image support is not production validation.

Keep deployment supervised. The API has no application authentication, which
is why the executed AWS route uses SSM without inbound web access. Do not use
this demo to autonomously accept/reject safety-critical hardware. Human review
must retain the original images and evidence. Real production data, acquisition
protocols, identity gating, access control, concurrency, backups and independent
evaluation are needed before broader use.

Final competition gaps are tracked in [readiness](../submission/READINESS.md):
the public demo URL, YouTube/Vimeo video embedding, Devpost teammate membership,
final rights/eligibility checks and actual Devpost submission.

## Final audit integrity changes

REST and MCP writers share a nonblocking OS file lock per inspection. MCP
mutators accept only created runs; generating the report finalizes the session,
with unfinished candidates sent to human review. The UI observes MCP sessions
without starting a second REST run. Terminal publication follows the final
awaited write, preventing stale completion writes from overwriting a review.

Supplying a secondary capture through `/views` or `/rerun` creates and starts a
new child. Both return the child inspection ID. Parent images, events and report
are retained, including if child startup fails. The child records its parent,
SHA256 input hashes and a capture event. Clients of `/views` must follow the
returned ID; that route no longer edits an old run in place.

Rejected operator reviews clear the final defect label in API/state/report.
Failed UI starts show Retry Start, and created state is distinct from a running
task. A conservative one-pixel clipped-pixel halo removes the demonstrated
glare artifact. A 15-pixel halo was rejected because it fragmented regions and
increased the fixed baseline's false positives from 50 to 53. The accepted
correction preserved all 30 cases' measured non-timing outputs.

Codex assisted development, research, fixes, tests and submission preparation.
It is not the runtime planner; the application uses the deterministic evidence
policy described above. Human authors remain responsible for the entry.
