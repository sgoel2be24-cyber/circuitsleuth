# CircuitSleuth — Team Update

**Shikhar Goel · Ishpreet Singh**  
OpenCV AI Competition 2026 · intended special consideration: Agentic Vision

## Thirty-second pitch

A suspicious mark on a circuit board might be a defect—or just glare or
misalignment. CircuitSleuth uses OpenCV 5 to find that mark, then decides what
evidence to collect next: test alignment, investigate illumination, compare a
second capture, or ask a human. Every decision comes with an inspection trail.
On our 30-case synthetic benchmark, adaptive verification reduced reported
false positives from 50 to 10 and raised macro F1 from 0.575 to 0.716. We are
Team Update: Shikhar Goel and Ishpreet Singh.

## Three-minute spoken pitch

**The problem — Shikhar**

When a PCB inspection flags a suspicious region, the important question is:
what evidence would tell us whether it is real? A single image can mix a
physical defect with glare, noise and alignment error. Reporting every
difference creates extra review work. Dismissing differences too aggressively
can hide real defects.

We built CircuitSleuth to investigate that uncertainty.

**The product — Ishpreet**

An operator supplies a reference board and a test image. OpenCV 5 aligns the
images and detects candidate changes. A bounded planning policy then selects
a follow-up action for each open region using the measured uncertainty,
severity, evidence quality and tool cost.

If alignment is suspect, it tests local registration. If illumination is
suspect, it tests that hypothesis. When a separate capture is available, it
compares that view. Reprocessing the same pixels is explicitly distinguished
from obtaining an independent capture.

The interface shows the real plan, tool results, image crops and final
verdicts. Missing evidence becomes a capture request or a human-review task.
A failed registration can end with “not evaluable.” Operators can inspect the
evidence, record a decision and export the report.

**Why the agent matters — Shikhar**

The next action depends on the OpenCV measurements and the evidence already
collected. It is a transparent, deterministic policy with a limited tool
budget. The same eight inspection tools are also available through MCP.

Our recent correctness work fixed the direction of ECC alignment and tightened
the evidence needed to clear a region. A conflicting second view now goes to
review. That matters because a visually cleaner alignment must not erase a
real defect from the final decision.

**Measured results and limits — Ishpreet**

On 30 seeded synthetic inspections, adaptive verification reduced reported
false positives from 50 to 10—an 80 percent reduction—and raised macro reported
F1 from 0.575 to 0.716. The trade-off is explicit: macro reported recall fell
from 0.893 to 0.782, and 27.3 percent of candidate verdicts required review.
These are synthetic results, not a production accuracy claim.

We have a working application, automated regression coverage and a verified
Linux container build. Real-board validation remains important: the small
external research check showed a substantial domain gap, and board-identity
checks still need improvement.

**Close — both**

CircuitSleuth makes the path from visual evidence to an inspection decision
visible and reviewable. We are Team Update—Shikhar Goel and Ishpreet Singh.

## AWS sentence: use only the version supported at presentation time

**Current, truthful version:** “The AWS deployment package is prepared. A real
AWS inspection is still pending account access and budget verification.”

**After an evidenced cloud run:** Replace that sentence with the actual AWS
service, region and inspection IDs from the saved evidence. Never describe the
local or GitHub Actions run as AWS execution.

## Evidence behind the numbers

- Current benchmark: `output/ecc-verification-fix/benchmark/results.json`.
- Method: 6 synthetic templates × 5 variants; same current OpenCV core for
  fixed and adaptive modes; macro metrics; IoU matching threshold 0.15.
- Review rate denominator: candidate verdicts, not inspections. F1 is not an
  “accuracy percentage.” Recall and review workload must accompany the FP claim.
- The earlier `evaluation/results.json` remains an historical snapshot; do
  not mix its 52 false positives with the current baseline's 50.
- `docs/ALIGNMENT_FIXES.md` records probes, unchanged research-capture outcomes
  and unresolved wrong-board acceptance. No COOL/Graviton claim is made.

This is a pitch document. Video production is deferred at the team's request.
