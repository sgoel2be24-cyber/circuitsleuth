## Inspiration

A suspicious mark on a circuit board can be a real defect, glare or alignment
error. Inspection operators need a useful next step when the first image is
inconclusive, along with a record of why the system reached its decision.

We are **Team Update — Shikhar Goel and Ishpreet Singh**. We built CircuitSleuth
to investigate visual uncertainty with OpenCV 5 and an auditable tool loop.

## What it does

An operator supplies a reference board and a test image, or selects a seeded
synthetic demonstration. OpenCV 5 aligns the images and detects candidate
changes. A bounded planning policy chooses the next action for each open region
using uncertainty, severity, evidence quality, estimated information gain and
cost.

Alignment concerns can trigger local registration. Illumination concerns can
trigger a threshold-based confound test. A separately supplied capture enables
an independent-view comparison. A missing capture can trigger a request for
more evidence and human review. Unreliable alignment can end with “not evaluable.”

The interface streams actual plan and tool events, shows image evidence and
allows operator decisions. Reports include verdicts, limitations and the review
trail. Reruns create a new inspection while preserving the original run.

## How we built it

The application uses Python 3.13, FastAPI, OpenCV 5.0.0, NumPy, SQLite, React,
TypeScript and Vite. OpenCV performs feature matching, RANSAC registration,
photometric verification, ECC refinement, difference analysis, topology and
regional verification. The same eight inspection tools are exposed over MCP.

Our deterministic planner is transparent and budget-bounded. Measured visual
flags and accumulated evidence change subsequent tool calls; a result with
decisive evidence can move directly to verification. This is an active
perception workflow with human control, without an LLM dependency.

The Docker container builds and runs in Linux CI. We prepared an EC2 deployment
with encrypted EBS, CloudWatch logs and an authenticated Systems Manager tunnel.
**Actual AWS execution remains pending:** the account currently redirects EC2
to its account-setup page. We do not claim local or CI execution as AWS proof.
No COOL or AWS Graviton implementation is claimed.

## Challenges we addressed

Image registration can appear convincing while aligning periodic traces to the
wrong features. We verify hypotheses photometrically and apply quality gates.
We also corrected ECC transform direction and tightened local alignment
evidence so unconstrained fitting cannot simply erase a real defect. Conflicting
local and separate-view evidence is sent to review.

Reprocessing existing pixels does not create optical detail. Our interface and
reports distinguish those tools from a separately supplied capture.

## Results and verification

On 30 seeded synthetic inspections, using the same current OpenCV core in fixed
and adaptive modes:

| Metric | Fixed inspection | Adaptive verification |
|---|---:|---:|
| Macro reported precision | 0.5208 | 0.8627 |
| Macro reported recall | 0.8933 | 0.7822 |
| Macro reported F1 | 0.5751 | 0.7155 |
| Reported false positives | 50 | 10 |
| Candidate verdicts requiring review | 0% | 27.27% |

The 80% reduction in reported false positives comes with lower reported recall
and added human-review work. Matching uses IoU 0.15. These are synthetic
benchmark results, not production PCB accuracy. The final audit reproduced all
30 non-timing outputs exactly.

Backend regression tests, frontend lint/build, actual MCP stdio calls and
container HTTP checks cover the working application. Six demo cases exercise
clear defects, a clean board, glare, alignment failure, missing views and a
limited tool budget. Reports, raw events, planning references and image crops
are exportable with hashes.

## What we learned and what is next

An inspection system must preserve uncertainty as carefully as it records a
positive finding. Our research also exposed substantial domain gap on a small
external DeepPCB check and existing wrong-board acceptance in some mismatch
controls. The current system is a supervised demonstration; real manufacturing
validation, stronger board identity, tiny-defect sensitivity and an integrated
capture rig remain future work.

Before final submission we still need the actual AWS run, judge-accessible
source/demo arrangements and the required team demonstration video. Video
production is deferred by our team for now. The pitch, technical report,
architecture, dependency locks, testing instructions and source package are
prepared.
