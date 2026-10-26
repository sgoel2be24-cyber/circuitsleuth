# Shikhar: final submission handoff

Updated **27 October 2026 IST**. Team Update: **Shikhar Goel and Ishpreet Singh**.

**The AWS execution requirement has been verified. The current code still has five open correctness findings. This handoff does not mark the entry submitted or the code fixed.**

The application tested and deployed was commit `6281c2be7d3832b26b3522202a5f5fea59af1825`. This documentation update does not change application code. Older documents describing AWS execution as pending are superseded by this handoff and the dated evidence below.

## Read these first

- [Open code findings and acceptance checks](../docs/REVIEW_2026-10-27.md).
- [Verified AWS execution and access limits](../docs/AWS_EXECUTION_2026-10-27.md).
- [Sanitized AWS verification record](evidence/aws-verification-redacted.json).
- [Reproduced review observations](evidence/review-reproductions.json).
- [Testing and setup](../README.md), [technical report](../docs/TECHNICAL_REPORT.md), and [deployment guide](../deploy/README.md).

## Verified already

- Windows backend suite: **103 passed**; frontend lint and production build passed.
- All **eight MCP tools** exercised over real stdio.
- Full **30-case synthetic benchmark** reproduced; this is not manufacturing validation.
- Actual EC2 HTTP smoke passed with **OpenCV 5.0.0**, including inspection, planning events, report and PNG crops.
- All **six AWS demo scenario behavior checks passed**; **72 evidence-file hashes** rechecked after downloading.
- Exact reviewed-commit CI succeeded: [run 40368694991](https://github.com/sgoel2be24-cyber/circuitsleuth/actions/runs/40368694991).

These results predate any subsequent application fixes. Rerun validation against the final code commit and regenerate source/runtime artifacts after changes.

## Complete in this order

1. **Fix the two high-priority audit/lifecycle issues:** prevent completed-run MCP mutation/restart, and attach new captures to a child inspection without modifying the original completed run.
2. **Fix the remaining three issues:** clipped-glare mask, rejected-review label, and failed-start retry. Add targeted regressions. Rerun the benchmark after changing the glare mask and report any metric changes honestly.
3. **Validate the final commit:** backend tests, frontend lint/build, MCP smoke, actual HTTP checks, six scenarios and CI. Redeploy the final application commit if application code changes; the AWS evidence currently identifies the older tested commit explicitly.
4. **Arrange judge access:** provide a working endpoint or explicitly arrange the allowed live screen-share. Current AWS access is private SSM; there is no public application URL. Do not paste a private Console URL as the judge endpoint.
5. **Refresh submission text:** AWS is verified in Stockholm; repository is public; deterministic policy proposes evidence-conditioned tools rather than exhaustively comparing every tool pair. Keep synthetic results, external generalization limits and human review visible. Update `DEVPOST.md`, `PROJECT_STORY.md`, `FORM_ANSWERS.json` and technical-report deployment wording before copying them into the portal.
6. **Create the final source ZIP from a clean committed checkout:** `python tools/package_submission.py --out CircuitSleuth-Team-Update-source.zip`. Verify its commit manifest and checksum, then upload the ZIP through the required portal field. Do not upload dependency folders, private AWS evidence or external research captures.
7. **Finish the required public/unlisted video (at most five minutes), portal fields, eligibility/rights checks, and final submission.** Verify the actual submitted status/receipt. A published project page or saved draft is not proof of contest submission.

The official dates API was previously checked as **27 October 2026, 12:15 p.m. IST**; reconfirm the portal deadline and leave upload time. Official event: https://opencv26.devpost.com/ . This handoff does not recheck the deadline or portal state.

## Evidence and AWS continuity

The full evidence ZIP is retained privately by Ishpreet and in the task-created private S3 bucket. Public summaries omit account IDs, IAM identity, bucket/resource identifiers and raw Console screenshots. The raw ZIP SHA256 is recorded in the AWS note so the private copy can be matched.

The approved demo uses Free Plan credits only, a USD 1 credit budget, and no paid-plan upgrade. Billing is delayed; this budget is not a hard billing cap. The host confirmed a stop scheduled for **27 October 2026, 06:27:14 a.m. IST**. That schedule is not evidence that the stop has happened. Recheck actual instance state before a demonstration; do not assume the six-hour session remains available. Stopping leaves storage/log costs; cleanup remains after evidence preservation and demo completion.

No code fixes, new public endpoint, new source release, video upload, teammate message or competition submission was performed as part of this handoff push.
