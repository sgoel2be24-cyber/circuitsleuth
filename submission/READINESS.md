# Competition readiness — 26 October 2026

Team **Update** · **Shikhar Goel and Ishpreet Singh**

Official source: [OpenCV AI Competition 2026](https://opencv26.devpost.com/).
The dated overview/rules/dates/judging/requirements snapshot is in
`requirements-snapshot.json`. Requirements from the site are submission
constraints, not authorization to register, accept terms or submit for the team.

## Deadline

The live deadline widget/API returns **27 October 2026, 06:45 UTC / 12:15 IST**.
The prose says 26 October 23:59 Pacific, fourteen minutes later. Work to the
**earlier 12:15 IST cutoff**, and leave upload time. No extension is assumed.

## Deliverables

| Official requirement | Current evidence / next step |
|---|---|
| Substantive OpenCV 5 analysis | Implemented; health, locked dependencies, CV source, regression suite |
| Meaningful AWS execution | **Pending**; account sign-in/balance checked; EC2/CloudFormation redirect to account-setup page; deployment blocked |
| Technical report | `docs/TECHNICAL_REPORT.md` with limitations and current results |
| OpenCV/AWS/agent architecture | Mermaid diagrams in technical report; AWS explicitly marked planned |
| Judge-accessible source | Private GitHub repo exists; judge invitation/access or required source ZIP delivery still pending |
| Pinned dependencies and instructions | Python/frontend locks, README, portable verifier, deployment guide, CI |
| Working endpoint OR arranged live screen-share | Private SSM demo route prepared; real cloud run and judge arrangement pending |
| Public/unlisted video ≤5 minutes | **Deferred at user's request**; still required for final entry |
| Evaluation including failures | Current 30-case benchmark, alignment probes, documented external domain gap, six-case HTTP evidence |
| Agentic Vision evidence | Source policy, workflow, exported raw events and planning references; intended award consideration |
| COOL award evidence | Not implemented; do not select or claim COOL |
| Final entry and eligibility/rights | Human review and actual submission pending; no submission performed by these scripts |

## What the judging weights imply

Technical execution 30%, innovation 20%, impact 20%, UX 10%, documentation and
presentation 10%, cloud/reproducibility/responsible AI 10%. The code and evidence
should support the same focused story: visual measurements change inspection
actions, results can be audited, uncertainty leads to review.
Do not make late unvalidated preprocessing changes to chase a headline score.

## Prepared handoff

- `PITCH.md`: thirty-second and three-minute pitch, both members credited.
- `DEVPOST.md`: submission draft with exact current metrics and pending AWS status.
- `deploy/aws-ec2-demo.template.json`: no-inbound EC2/SSM/CloudWatch template.
- `tools/export_demo_evidence.py`: six real API inspections with behavior checks,
  full reports/events, planning references, PNG evidence and hashes. It does not
  itself prove AWS hosting or benchmark accuracy.
- `tools/package_submission.py`: Git-tracked source ZIP and source/hash manifest;
  excludes runtime data, credentials, dependencies and third-party DeepPCB captures.

Create the judge archive after committing:

```bash
python3 tools/package_submission.py --out /tmp/CircuitSleuth-Team-Update-source.zip
```

Inspect its manifest and upload the archive through the required submission
channel. A generated local ZIP does not make the private repository accessible
to judges. The archive intentionally omits the external research images;
research code, provenance and recorded findings remain, and core synthetic
fixtures and generation instructions are included.

## Latest user instruction: zero cash spending

**₹0 out of pocket. AWS Free Plan credits only.** No paid-plan upgrade, paid
support, card-billed deployment or paid-only service is authorized. The prior
half-of-remaining-credits limit remains a credit-consumption limit. See
[the team handoff](../HANDOFF.md) for the full latest context.

## Earlier budget instruction (subject to the zero-cash rule above)

User requested at most **50% of usable remaining AWS credits** and a nearby
region for low latency. Provisional region: Mumbai `ap-south-1`. Account access and the free-plan
credit balance were checked locally; the numeric deployment ceiling was
computed without bundling account billing details in the source package.
Service eligibility and real resource costs still need checking. No paid
resources have been launched.

## Account-access finding

Billing and Free Tier were readable, but EC2 and CloudFormation in Mumbai
redirected to AWS's “Complete your account setup” page. CloudShell also failed
to create an environment. AWS lists incomplete registration/activation or
free-plan limitations as possible causes; the exact cause is not established.
Payment/identity verification and any paid-plan upgrade must be completed or
explicitly decided by the account owner. No service plan was upgraded and no
billable resource was created. The prepared deployment can continue after
service access is available.

## Final audit supersedes earlier progress snapshots

See `docs/FINAL_AUDIT.md` for the renewed 101-test verification, exact 30-case
metric reproduction, real upload/SSE/review/rerun checks and the final readiness
decision. `PROJECT_STORY.md` and `FORM_ANSWERS.json` are prepared.

The Devpost project page was published automatically by its update action when
saving the prepared story: https://devpost.com/software/circuitsleuth-team-update .
The competition entry remains unsubmitted and has no video URL. Judge source/demo
access and meaningful AWS execution remain outstanding; the earlier deferred-video
instruction is still in force.

## Later activation observation

Following “Complete your AWS registration” displayed the AWS confirmation page
“We are activating your account,” with an activation email to follow. EC2 was
still blocked on the immediate retry in Stockholm. No payment or plan-upgrade
action was performed. This is pending activation evidence, not cloud execution.
AWS's new sign-up experience can restrict a project to an assigned region; check
AWS Settings before assuming Mumbai is available.
