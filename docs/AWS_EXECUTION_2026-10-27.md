# Verified AWS execution: 27 October 2026 IST

This note supersedes older repository statements that AWS activation prevented execution. The approved credits-only deployment succeeded in **Stockholm, eu-north-1**. CloudFormation reached CREATE_COMPLETE; a **t3.small** with **30 GiB encrypted gp3** ran the application container. Authenticated Systems Manager access was used. No inbound web/SSH ports were opened; the application bound to `127.0.0.1:8080`. There is **no public judge endpoint**.

## Captured execution

Recorded **2026-10-26T19:06:35Z / 27 October 2026, 00:36:35 IST**:

- Source: `6281c2be7d3832b26b3522202a5f5fea59af1825`.
- Runtime ZIP SHA256: `8667f22d7e719bbeec26e3ee5d0e26c427cfd8f8e57826cf62e4cd0a650f7291`; all 76 source-manifest files verified locally, and bootstrap verified the archive checksum before building.
- Docker image: `sha256:d175223d53daa0fd7d6d0909d679a5b0b6d35d51f0850ba6c9855b747f00aa8e`.
- Real HTTP smoke **passed**, OpenCV **5.0.0**, three regions and 23 events. This exercised health, SPA deep link, create/start/complete, report, planning events and PNG crops.
- All **six** scenario behavior checks passed: clear defects, clean board, ambiguous glare, registration failure, missing second view and multiple-region/tool-budget behavior.
- Reports, events, planning references and image crops were downloaded; all **72 evidence-file hashes matched** locally.

[Sanitized verification record](../submission/evidence/aws-verification-redacted.json) preserves scenario IDs/results and source/runtime identity. It is a sanitized copy of the captured host receipt, not independent cloud attestation. The private original archive SHA256 is `47b1d21fe3e62cd4e3a2aa3cbc1c03f6dabf3f2b568881da89b7a7aad6676008`. The original packet remains with Ishpreet and in private S3; it includes AWS resource/account identifiers, so it is not committed here.

The general scenario exporter still emits `aws_execution_verified=false` because the exporter cannot attest its hosting. Actual cloud execution was established separately through authenticated Console/SSM observations, stack state and host receipt. Application code was not changed to manufacture that flag.

## Access and cost continuity

Use the [deployment guide](../deploy/README.md) with the actual Stockholm region and instance target from the private handoff/account. A local CLI/Session Manager tunnel was not established on Ishpreet's machine; on-instance HTTP execution was verified. Arrange a judge endpoint or the permitted live screen-share separately. This public note is not an access grant.

The approved scope was one supervised Free Plan credits-only demo with a **USD 1 credit budget**, no paid-plan upgrade. Billing is delayed; final credit use was not established and the budget is not an enforceable cap. Private S3 uses blocked public access and encryption; CloudWatch logs have seven-day retention.

The host confirmed a shutdown scheduled for **27 October 2026, 06:27:14 IST / 00:57:14 UTC**. This records the schedule, not proof that shutdown has since occurred. Recheck instance state before a demo; any later restart needs its own stop plan within authorized spending. EBS, S3 and logs remain after instance stop. Preserve evidence before task-specific cleanup; cleanup has not been performed by this handoff.

The deployment did not repair the [five code findings](REVIEW_2026-10-27.md), provide judge access, generate a final release, upload a video or submit the competition entry. Any code fixes require new validation and deployment evidence identifying the final application commit.
