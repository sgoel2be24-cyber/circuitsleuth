# Deployment

## Verified status, 2026-10-25

| Component | Evidence and limits |
|---|---|
| Local environment | Python 3.13.1, OpenCV 5.0.0; `pip check` reports no broken requirements. See the project verification report for current test and UI results. |
| Backend dependency lock | `backend/requirements.lock.txt` pins runtime and test dependencies from the installed environment. Windows-only dependencies have platform markers. A fresh Linux installation is not yet verified. |
| Container | Dockerfile updated and reviewed; build and execution remain **unverified** because Docker is unavailable here. |
| AWS | **Unverified**. No AWS workload was created or billed during this work. |
| Durable cloud storage | **Not implemented**. SQLite and artifacts are local to the process filesystem. |

AWS execution is a competition requirement. A locally working application alone does
not satisfy it. Record a real cloud inspection and its logs before claiming compliance.

## Reproduce locally

Use Python 3.13 and Node 24. The frontend lock file is installed with `npm ci`.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.venv\Scripts\python.exe tools/generate_dataset.py
cd frontend
npm ci
cd ..
powershell -ExecutionPolicy Bypass -File scripts/verify_local.ps1
```

Add `-IncludeMcp` to run the independent MCP stdio smoke test; no API server
is needed. On macOS/Linux, use `.venv/bin/python scripts/verify_local.py
--include-mcp` (on one line). The verifier does not create cloud resources.

## Run the container locally

```bash
docker compose -f deploy/docker-compose.yml up --build
# http://localhost:8080 — API and UI from one process
```

The build uses Node 24, Python 3.13, the frontend lock file and the exact backend
lock. Base-image tags are release families, not immutable digests. Resolve and
record their digests before a reproducible production release. Uvicorn explicitly
uses the portable h11 transport without optional WebSocket dependencies; the
application streams events using SSE.

Startup generates the deterministic demo set in the configured data directory.
A generation failure prevents the API from starting. `exec` forwards container
termination signals to Uvicorn. Compose persists SQLite and artifacts in a named
volume.

After a successful build, verify:

1. `GET /api/health` returns `status: ok` and `opencv_version: 5.*`.
2. Open `/new`, complete a demo, download its report and reload its workspace URL.
3. Confirm API inspection status, candidate artifacts and actual event logs.
4. Restart the container and confirm completed inspection history survives.

## AWS deployment template — requires authorization and actual execution

The following commands create billable resources. They are provided for an
authorized deployment; they have **not** been executed or validated here.
Use one region consistently and replace every placeholder.

```bash
aws ecr create-repository --region <REGION> --repository-name circuitsleuth
docker build -f deploy/Dockerfile -t circuitsleuth:<IMAGE_TAG> .
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
docker tag circuitsleuth:<IMAGE_TAG> <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/circuitsleuth:<IMAGE_TAG>
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/circuitsleuth:<IMAGE_TAG>
```

Create an IAM ECR access role trusted by `build.apprunner.amazonaws.com` with the
managed App Runner ECR read policy. This is the **access role**, not a runtime
instance role. Copy `apprunner-service.example.json` to a local configuration,
fill in account, region, image tag and access-role ARN, then:

```bash
aws apprunner create-service --region <REGION> --cli-input-json file://deploy/apprunner-service.local.json
```

The template follows AWS's documented
[source configuration](https://docs.aws.amazon.com/apprunner/latest/api/API_SourceConfiguration.html),
[ECR access-role configuration](https://docs.aws.amazon.com/apprunner/latest/api/API_AuthenticationConfiguration.html)
and [image environment variables](https://docs.aws.amazon.com/apprunner/latest/api/API_ImageConfiguration.html).

The example uses port 8080, HTTP health check `/api/health`, 1 vCPU and 2 GB RAM.
These are starting settings; validate latency and memory with the real workload.
App Runner exposes container stdout through CloudWatch; preserve logs tied to the
inspection ID together with report, service URL, region, image digest and timestamp.
Cloud-provider service metadata alone does not prove an inspection ran there.

App Runner storage is ephemeral. The example uses `/tmp/circuitsleuth`; history and
artifacts can disappear on replacement and are not shared between instances.
Keep a supervised single-instance demo or implement external storage before using
multiple instances or claiming durable cloud history. S3 and shared database
integration remain future work. Do not expose an unauthenticated upload API as a
general production service; the current target is a bounded competition demo.

## Configuration

Settings use the `CIRCUITSLEUTH_` prefix (`backend/app/config.py`): data directory,
budgets, thresholds, CORS origins and input limits. Configure
`CIRCUITSLEUTH_DATA_DIR` consistently for generation and runtime. Do not place AWS
credentials, `.env` files, inspection history or personal uploads in an image.
