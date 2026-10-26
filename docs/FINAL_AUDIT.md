# Final readiness audit — 26 October 2026

Team **Update** · **Shikhar Goel and Ishpreet Singh**

**Decision: the application is ready for a supervised synthetic demonstration;
the competition submission is not ready yet.** Required AWS execution, video
and judge-delivery arrangements remain incomplete. This audit does not claim
production PCB readiness.

## Fresh verification

| Check | Result and evidence |
|---|---|
| Locked Python environment / OpenCV 5 | Passed; OpenCV 5.0.0, Python 3.13.15 |
| Backend regressions | **101 passed**, two Windows-only tests skipped on macOS |
| Frontend lint and production build | Passed |
| MCP | All eight tools executed over actual stdio |
| 30-case benchmark | All non-timing outputs reproduced exactly |
| Six API demo scenarios | Passed with reports, raw events, planning references, PNG crops and hashes |
| Real three-image upload | Completed with evidence-backed findings; source recorded as upload |
| Invalid images / invalid budgets | HTTP 400 / 422, respectively |
| Missing API and asset routes | HTTP 404; frontend deep links still return the SPA |
| SSE replay | Persisted planning events replayed and terminal event delivered |
| Operator decision / downloaded JSON | Confirmed verdict and resolved review task agree in actual browser download |
| Rerun isolation | New inspection ID; original reviewed report and event hashes unchanged |
| Restart persistence | Existing reports/ledger remained available after API restart |
| Desktop and mobile UI | Scenario launch, review, report, rerun and navigation checked; no broken images or page overflow at desktop and 390px mobile override |
| Browser console | No captured warnings/errors during these journeys |
| AWS template | cfn-lint 1.58.0 passes; template has not run on AWS |
| Container | Pinned CI workflow builds Docker and runs HTTP + six-scenario evidence export; inspect the final main-branch run |
| Source/runtime packages | Source commit and per-file hashes embedded; external DeepPCB captures, dependencies, credentials and runtime history excluded |

Logs/results: `output/final-audit/`. Browser captures and observations:
`output/playwright/final-audit/`. The earlier evidence directories remain intact.
CI: [main-branch verification](https://github.com/sgoel2be24-cyber/circuitsleuth/actions/workflows/verify.yml).
Local Docker remains unavailable; container execution is established by Linux CI.

## Final polish fix

The audit reproduced a dashboard ordering problem: inspections created in the
same second could show an older run as “latest.” The SQLite query now breaks
timestamp ties by insertion order, newest first. One regression verifies ties,
updates to older runs and the requested list limit. No schema, API, ID, artifact
path, CV module, preprocessing threshold or planner behavior changed.

## Re-evaluated metrics

Same current OpenCV core, six templates × five seeded variants, IoU 0.15:

| Metric | Fixed | Adaptive |
|---|---:|---:|
| Macro reported precision | 0.5208 | **0.8627** |
| Macro reported recall | 0.8933 | 0.7822 |
| Macro reported F1 | 0.5751 | **0.7155** |
| True positives / false positives / false negatives | 44 / 50 / 6 | 42 / 10 / 8 |
| Candidate review rate | 0% | 27.27% |
| Micro reported precision | 0.4681 | 0.8077 |
| Micro reported recall | 0.8800 | 0.8400 |
| Micro reported F1 | 0.6111 | 0.8235 |

Macro metrics average inspections and include the benchmark's empty/refusal-case
conventions. Micro metrics pool TP/FP/FN; they do not replace the original
headline definition. The 80% reported false-positive reduction costs two
additional false negatives and adds review work. There is no defined binary
“accuracy” percentage because this localization benchmark has no true-negative
population. No cloud timing, production accuracy or calibrated confidence is
established. Existing domain-gap, tiny-defect and board-identity limitations in
`TECHNICAL_REPORT.md` remain open.

## Current external state

- **AWS:** sign-in works, but Mumbai EC2 still redirects to “Complete your
  account setup,” and CloudShell cannot create its environment. The page lists
  unfinished registration/activation or free-plan limitations; it does not
  identify the exact cause. No plan upgrade or billable resource was created.
  The owner must handle any identity/payment verification. The existing budget
  rule remains at most half usable remaining credits.
- **Devpost:** the previously empty entry now has the prepared title, tagline,
  story and technology tags. Devpost's update action **published the project
  page automatically**: [CircuitSleuth — Team Update](https://devpost.com/software/circuitsleuth-team-update).
  Its hackathon entry remains **unsubmitted** (`submitted_at: null`). The page
  states that AWS execution and video are pending. No terms were accepted and
  no contest entry was submitted during this audit.
- **Source:** GitHub repository is private. The generated source ZIP is ready
  for delivery, but judge access is not established by merely generating it.
- **Video:** no video was made, following the team's instruction. The pitch is
  prepared; a public/unlisted video of at most five minutes is still mandatory.
- **Demo:** a private SSM route is prepared. A public endpoint or an actual
  live screen-share arrangement has not been provided to judges.

## Final handoff

Prepared: `submission/PITCH.md`, `PROJECT_STORY.md`, `DEVPOST.md`,
`FORM_ANSWERS.json`, this report, the technical report, architecture, locked
build/test instructions, deployment template, evidence and source/runtime ZIPs.

To change the submission decision to ready:

1. Resolve AWS service access, run an actual inspection there and save cloud
   identity/configuration/log evidence tied to its inspection IDs.
2. Add the required judge-accessible video when the team is ready to make it.
3. Deliver judge source access and a working demo endpoint or arranged live
   screen-share; fill the prepared submission fields and required ZIP upload.
4. Review eligibility, rights and final declarations, then explicitly authorize
   the final submission. No submission is inferred from this audit request.

The refreshed official API deadline is **27 October 2026 at 06:45 UTC /
12:15 p.m. IST**. The prose gives a cutoff fourteen minutes later; use the
API/widget's earlier time and leave an upload margin. Requirements/date evidence
is in `output/final-audit/hackathon-recheck.json` and the
[official event page](https://opencv26.devpost.com/).
