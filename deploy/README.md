# Deployment

## Verified status — 26 October 2026

The Linux GitHub Actions workflow successfully installed the dependency locks,
built `deploy/Dockerfile` and completed an actual HTTP inspection with report,
events and PNG evidence. This verifies the container, not an AWS deployment.
The local Docker daemon is unavailable. AWS execution is still pending.

## Local container

```bash
docker compose -f deploy/docker-compose.yml up --build
python3 tools/http_smoke_test.py --base-url http://127.0.0.1:8080
python3 -m tools.export_demo_evidence --out /tmp/circuitsleuth-demo-evidence
```

The evidence exporter creates six synthetic inspections. Use disposable storage.
It writes full reports, audit events, planning references, PNG crops and hashes.
Partial/failed exports remain on disk for diagnosis; reruns need a new directory.

## AWS: supervised EC2 demo

`aws-ec2-demo.template.json` supplies a concrete alternative for new AWS accounts.
[App Runner stopped accepting new customers on 30 April 2026](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html).
The old App Runner example is retained only for existing customers.

The template creates one x86 EC2 `t3.small`, a 30 GiB encrypted gp3 root volume,
an instance role, a security group with **no inbound rules**, and seven-day
CloudWatch logs. Docker publishes only `127.0.0.1:8080`. AWS Systems Manager
provides authenticated shell/port forwarding. The existing application needs no
cloud-specific pipeline changes. A host-mounted data directory survives
container restart and EC2 stop/start; stack deletion deletes that root volume.
This is a single-instance demonstration, without high availability or backups.

The instance builds the existing Dockerfile from a SHA-256-checked private S3
source ZIP. Its role can read only that source object, write only the stack's
evidence prefix and send logs to its log group, plus the standard SSM managed
node permissions. IMDSv2 is required. No SSH key or public application endpoint
is created. The public IPv4 address provides outbound internet in an existing
public subnet; it is billable even though ingress is closed.

### Strict spending rule

**₹0 out of pocket: Free Plan credits only.** No paid-plan upgrade, paid
support, paid-only service or card-billed usage is authorized. The half-credit
ceiling below is not a cash budget. Stop if the account requires a paid upgrade.
Check the assigned project region in AWS Settings before using the example
Mumbai commands; newer sign-up accounts may have a fixed region. The latest
registration page said activation is in progress, and EC2 remained blocked.
See [HANDOFF.md](../HANDOFF.md) for current account status and team instructions.

### Account and cost gate

Complete AWS sign-in/MFA yourself. Then inspect Billing → Credits and Bills:
credit remaining amount, expiration, eligible services, and existing charges.
The user's requested ceiling is **half of the usable remaining credits**.
Check the EC2, EBS, public IPv4, S3 and CloudWatch rates for `ap-south-1` (Mumbai)
before execution, including already-running account resources. No balance or
free-tier eligibility is assumed. Credits are not a prepaid cash wallet.

The template uses standard T3 credits and schedules an automatic stop six hours
from first boot. **That is not a hard spending cap**: EBS, public IPv4, S3 and
logs can keep billing, and a later manual restart needs a new shutdown timer.
Delete the stack and source/evidence objects after preserving needed results.
AWS Budgets alerts can lag and do not impose a universal spending limit.

### Prepare source locally (no cloud resources)

Commit changes first. Python standard library and Git are sufficient:

```bash
python3 tools/package_submission.py --runtime --out /tmp/circuitsleuth-runtime.zip
```

The ZIP has a source commit and per-file hashes. It excludes dependencies,
inspection data, environment files and research captures. Keep the printed SHA.
Upload it to a private S3 bucket in the chosen region using the AWS console or
AWS CLI after the budget is checked. Use an immutable source object key.
Do not upload the original working directory or credentials.

### Deploy after account and budget checks

Use an authenticated AWS CLI, including CloudShell if preferred. Set the region
explicitly. Supply a VPC and public subnet in the same VPC, with an internet
route; the template does not create a VPC, NAT gateway or load balancer.
Fill the template parameters with the private source bucket, object key and
printed SHA256. The launch creates billable resources and an instance IAM role.

```bash
aws cloudformation validate-template --region ap-south-1 \
  --template-body file://deploy/aws-ec2-demo.template.json
aws cloudformation deploy --region ap-south-1 \
  --stack-name circuitsleuth-demo \
  --template-file deploy/aws-ec2-demo.template.json \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides VpcId=VPC_ID SubnetId=SUBNET_ID \
    SourceBucket=BUCKET SourceKey=SOURCE_KEY SourceSHA256=ZIP_SHA256
aws cloudformation describe-stacks --region ap-south-1 --stack-name circuitsleuth-demo
```

CloudFormation completion alone does **not** mean Docker finished building.
In EC2 → Connect → Session Manager, check:

```bash
sudo tail -100 /var/log/circuitsleuth-bootstrap.log
sudo docker ps
sudo docker exec circuitsleuth python tools/http_smoke_test.py
```

Failure logs remain on the host. AMI resolution, quotas, IAM/SCP permissions,
network access, image registries and dependency availability must be verified
by the real deployment. This template has been statically checked, not launched.

### Inspect and preserve proof

On the instance, run from a Session Manager session (replace BUCKET):

```bash
sudo docker exec circuitsleuth python -m tools.export_demo_evidence \
  --out /app/data/aws-evidence
sudo aws sts get-caller-identity --region ap-south-1
sudo aws s3 cp /var/lib/circuitsleuth/aws-evidence/ \
  s3://BUCKET/evidence/circuitsleuth-demo/ --recursive --sse AES256 --region ap-south-1
```

Record the EC2 instance ID, region, resolved AMI, source ZIP SHA and commit,
Docker image ID, command output, inspection IDs, timestamps and CloudWatch log
links in a separate cloud-run record. Download the evidence with an authorized
operator account. Redact account identifiers from public pitch material.
The exporter deliberately keeps `aws_execution_verified: false`: a local API
cannot certify its own hosting. Tie its artifacts to AWS-side evidence before
claiming completion of the competition's cloud requirement.

For a browser demonstration, install the official AWS CLI Session Manager plugin
on the operator's machine and use [AWS's port-forwarding procedure](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html):

```bash
aws ssm start-session --region ap-south-1 --target INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

Open `http://127.0.0.1:8080`. Judge delivery uses an **arranged live screen-share**
with this private route; that arrangement is still pending. A public link would
require application authentication and a separately reviewed exposure plan.

### Cleanup

Preserve the reports first: deletion destroys the root disk and its history.
Then delete the demo stack, wait for deletion, and remove only the source/evidence
objects created for this demo. The pre-existing S3 bucket is outside the stack.

```bash
aws cloudformation delete-stack --region ap-south-1 --stack-name circuitsleuth-demo
aws cloudformation wait stack-delete-complete --region ap-south-1 --stack-name circuitsleuth-demo
```

## Configuration and reproducibility

Python 3.13 / Node 24, `backend/requirements.lock.txt` and frontend `npm ci` are
used in CI and Docker. Base-image tags are release families, not immutable
image digests; preserve the actual image ID/digest with the cloud record.
`CIRCUITSLEUTH_DATA_DIR` controls persisted data. Never place secrets, personal
uploads or local inspection history in the image. The demo does not implement
multi-instance storage, S3 runtime artifact storage or production authentication.
