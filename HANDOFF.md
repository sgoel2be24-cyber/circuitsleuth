# CircuitSleuth handoff for Ishpreet

> **27 October 2026 update — Shikhar:** start with the [current submission handoff](submission/SHIKHAR_HANDOFF.md). AWS execution is verified; five code findings and final judge/video/portal delivery remain open. Older AWS-pending or private-repository statements below are historical and superseded by that handoff.

Updated 26 October 2026. Team **Update**: **Shikhar Goel and Ishpreet Singh**.

The application is verified for a supervised synthetic demonstration. **The
competition entry is not yet ready to submit.** This document captures the
project state and decisions needed to continue without the original chat.

## Read these first

| File | Purpose |
|---|---|
| [Final audit](docs/FINAL_AUDIT.md) | Test evidence, current metrics, scope and remaining blockers |
| [README](README.md) | Install, start and understand the application |
| [Technical report](docs/TECHNICAL_REPORT.md) | OpenCV/agent/AWS architecture and limitations |
| [Readiness checklist](submission/READINESS.md) | Competition deliverables and current status |
| [Pitch](submission/PITCH.md) | Thirty-second and three-minute spoken pitch with both credits |
| [Project story](submission/PROJECT_STORY.md) | Text saved to the Devpost project page |
| [Form answers](submission/FORM_ANSWERS.json) | Prepared submission values; not a submitted entry |
| [Deployment guide](deploy/README.md) | Docker, proposed private AWS demo, evidence and cleanup |
| [Research](research/pipeline-improvements/REPORT.md) | Ablations, failure cases and treatments not promoted |

## Repository and verified version

- Working repository: https://github.com/sgoel2be24-cyber/circuitsleuth — private.
- Original source: https://github.com/ISHPREET0101/circuitsleuth . Its history is
  retained; locally it is named `source-origin`. Work was pushed to the new
  repository's `main`, not back to that original repository.
- Latest tested application-code commit before this documentation handoff:
  `0957ce394c5477b2ecd35a238e0d5a6e59c58721`.
- That commit passed [Linux/container CI](https://github.com/sgoel2be24-cyber/circuitsleuth/actions/runs/40332338219).
  The current main-branch workflow also runs after this handoff update.
- Source/runtime ZIPs, checksums and a verification receipt are distributed
  through the repository's [Releases page](https://github.com/sgoel2be24-cyber/circuitsleuth/releases).
  Archives contain a `SOURCE_MANIFEST.json` identifying their commit and hashes.
- GitHub read access must be granted before a teammate can clone a private
  repository or download its release assets. Team credit in documents does not
  grant repository or Devpost membership.

## What was changed and preserved

1. Initial UI polish repaired production build, review/report synchronization,
   ledger browsing, mobile overflow and reruns. A rerun creates a fresh ID and
   preserves the earlier inspection's evidence.
2. CV correctness work repaired ECC warp direction and local intensity units,
   used common valid support and context outside the candidate region, and
   required reliable evidence before clearing a region. Conflicting local and
   separate-view evidence goes to review. See [alignment fixes](docs/ALIGNMENT_FIXES.md).
3. Tests and pinned CI now cover backend, frontend, actual MCP stdio, Docker
   build, actual API inspections, reports, events and PNG evidence.
4. `tools/export_demo_evidence.py` exports all six real API demo scenarios with
   reports, raw events, planning references, crops and hashes.
5. `tools/package_submission.py` packages tracked source, excluding credentials,
   runtime history, installed dependencies and third-party DeepPCB captures.
6. The final audit fixed same-second ledger ordering using insertion order as
   a tie-breaker. A regression covers ties, updates and the list limit.

Original source history, original benchmark files and research evidence were
preserved. The last polish change did not alter the CV modules, planner, API,
schemas, IDs, artifact routes or dependency locks. There is no promoted broad
preprocessing redesign or optional LLM planner.

## Verified results

The final local and independently extracted source-ZIP checks passed:
**101 backend tests**, two Windows-only tests skipped on macOS, frontend
lint/build, and all eight MCP tools over stdio. Linux CI built and exercised the
actual Docker container. Local Docker was unavailable; no local Docker run is
claimed.

Real API/browser checks covered three-image uploads, all six demo cases,
invalid inputs, SSE replay, operator decisions, JSON download, fresh rerun IDs,
unchanged original report/events, restart persistence and desktop/mobile UI.
Evidence: `output/final-audit/` and `output/playwright/final-audit/`.

The 30-case benchmark reproduced all non-timing outputs exactly:

| Metric | Fixed inspection | Adaptive verification |
|---|---:|---:|
| Macro reported precision | 0.5208 | 0.8627 |
| Macro reported recall | 0.8933 | 0.7822 |
| Macro reported F1 | 0.5751 | 0.7155 |
| TP / FP / FN | 44 / 50 / 6 | 42 / 10 / 8 |
| Candidate review rate | 0% | 27.27% |

Data: six synthetic templates × five variants; IoU 0.15. These are localization
and verdict metrics, not production accuracy. Macro averages include the
benchmark's empty/refusal conventions. Fewer false positives come with lower
reported recall and more review. Current JSON: `output/final-audit/reevaluation.json`.
The old `evaluation/results.json` has baseline FP 52; keep it as historical and
do not mix it with the current baseline FP 50.

Known limitations remain: 48 research captures had unchanged TP/FP/FN 87/22/33
before and after correctness fixes; two of four mismatch controls were wrongly
accepted by both versions. A six-pair external DeepPCB check matched one of
thirty annotations. Small defects below the existing area threshold can be
missed. Extra ORB fallback and blanket CLAHE were not promoted because research
showed wrong-board/false-positive regressions. This is not a validated
manufacturing inspection system.

## Run locally

Python **3.13**, Node **24**, Git. From a clone on macOS/Linux:

```bash
git clone https://github.com/sgoel2be24-cyber/circuitsleuth.git
cd circuitsleuth
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
npm --prefix frontend ci
.venv/bin/python scripts/verify_local.py --include-mcp
.venv/bin/python tools/generate_dataset.py
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8100 --http h11 --ws none
```

The verifier builds the frontend, which the same server serves at
`http://127.0.0.1:8100`. No provider API key or cloud account is required.
On Windows use `py -3.13 -m venv .venv`, then replace `.venv/bin/python` with
`.venv\Scripts\python.exe`. Install the same locks with `npm ci`.

The six scenarios are clear defects, clean board, glare, mismatched-board
registration failure, no second view and multiple regions with a tool budget.
For new audit/demo evidence, use disposable storage and an unused output path:

```bash
.venv/bin/python tools/http_smoke_test.py --base-url http://127.0.0.1:8100
.venv/bin/python -m tools.export_demo_evidence --base-url http://127.0.0.1:8100 --out /tmp/circuitsleuth-evidence-new
```

These commands create inspections. Keep benchmarks and tests separate from
history that should be preserved. MCP setup is documented in `docs/MCP.md`.

## Latest AWS and spending instructions — take precedence over older notes

**Shikhar's cash budget is ₹0. Use Free Plan credits only.** No paid-plan
upgrade, paid support, card-billed usage or paid-only service is authorized.
The earlier limit of half usable remaining credits is a limit on consuming
credits, not permission to charge money. No AWS resources have been created.

Billing/sign-in worked, but EC2 and CloudFormation in Mumbai redirected to
“Complete your account setup”; EC2 in Stockholm did too, and CloudShell failed
to create an environment. Following the existing “Complete your AWS registration”
link then displayed **“We are activating your account”**, with an activation
email promised. An immediate EC2 retry was still blocked. No payment fields,
terms acceptance or upgrade action was performed. Pending activation is directly
observed; the page does not establish that buying a plan is necessary.

AWS's newer sign-up experience can restrict projects to an assigned region.
Check AWS Settings → Project → Additional Info for the actual region before
using deployment commands. Mumbai is provisional; it is not proven available.
The prepared guide's `ap-south-1` commands must be adapted consistently if the
account uses a different supported region.

The EC2/SSM/CloudWatch template is statically validated, not deployed. It uses
an encrypted host volume, loopback-only web port, no inbound security-group
rules and a six-hour initial stop. It does not provide a universal cost cap or
backups. Confirm Free Plan eligibility of every resource before launching.

If this account remains blocked, a teammate's already activated Free Plan with
usable credits is a possible alternative **if available and authorized**. The
local demo remains a zero-cash fallback. Another hosting provider alone does
not meet the competition's mandatory meaningful AWS execution requirement.
Do not invent a successful cloud run from CI, local execution or an environment
flag. App Runner is closed to new customers; no COOL/Graviton claim is supported.

Sources: [AWS Free Plan](https://aws.amazon.com/free/),
[EC2 Free Tier](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html),
[project regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html).

## Submission status and remaining sequence

Project page: https://devpost.com/software/circuitsleuth-team-update . Saving
its prepared title/story through Devpost's update action automatically made the
project page public. **The hackathon entry remains unsubmitted**, and no final
terms/declarations were accepted. The public text states AWS and video are
pending. Both team members are credited in the story and pitch; actual Devpost
team membership still needs verification.

The user requested **pitch only for now; do not make the video yet**. This
instruction remains in force. A public/unlisted video of at most five minutes
is nevertheless required before final submission.

Remaining work:

1. Resolve free account service access, perform an actual AWS inspection and
   retain hosting/configuration/log evidence tied to its inspection IDs.
2. When the team authorizes video production, record both members, the working
   app, architecture and principal results in at most five minutes.
3. Provide judge-accessible source and an endpoint or arrange a live
   screen-share. A private repo or local ZIP alone has not delivered access.
4. Verify team membership/eligibility/third-party rights and use the prepared
   repository/testing answers plus required source ZIP upload. Get explicit
   final submission authorization; the current request only asks for a handoff.

Official API/widget deadline last checked: **27 October 2026, 06:45 UTC /
12:15 p.m. IST**. Prose gives a later time by fourteen minutes; use the earlier
cutoff and recheck the official site before submitting. Requirements snapshots
are in `submission/requirements-snapshot.json` and
`output/final-audit/hackathon-recheck.json`.

## Artifact and data notes

The private repository includes the original research and provenance. The
judge-source ZIP deliberately omits external DeepPCB images. The project MIT
license does not relicense third-party datasets. Never commit AWS credentials,
account identifiers, `.env` secrets, personal uploads, runtime databases or a
full private chat/vault export. This handoff preserves project context without
those materials.

Release ZIP manifests identify the exact packaged commit. The verification
receipt distinguishes the tested application baseline from a later docs-only
handoff commit, and links its CI run. Installed dependencies and original
working-directory run databases are regenerable or private local state, not
handoff source.
