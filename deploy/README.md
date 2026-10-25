# Deployment

## Honest status (read this first, judges)

| Component | Status |
|---|---|
| Local execution (Python 3.13, OpenCV 5.0.0) | ✅ verified — all tests, benchmarks and UI journeys ran locally |
| Container build (`deploy/Dockerfile`) | ⚠️ provided but **unverified** — Docker is not available in the build environment |
| AWS App Runner / ECR execution | ❌ **unverified** — no AWS credentials were configured; no paid services were created |
| S3 artifact storage | ❌ not implemented (local filesystem + SQLite instead); see "AWS path" below |

Per the competition requirement we state plainly: **the core OpenCV processing in the
submitted demo runs locally, not on AWS.** The architecture (stateless FastAPI +
container image) is App Runner-ready, and the container path below is the intended
deployment. Nothing in the submission claims AWS execution that did not happen.

## Run the container locally

```bash
docker compose -f deploy/docker-compose.yml up --build
# → http://localhost:8080  (API + UI in one process)
```

## AWS path (intended, unverified)

1. Build and push the image to Amazon ECR:

   ```bash
   aws ecr create-repository --repository-name circuitsleuth
   docker build -f deploy/Dockerfile -t circuitsleuth .
   docker tag circuitsleuth:latest <account>.dkr.ecr.<region>.amazonaws.com/circuitsleuth:latest
   aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
   docker push <account>.dkr.ecr.<region>.amazonaws.com/circuitsleuth:latest
   ```

2. Create an App Runner service from that image (console or CLI), port 8080,
   health check path `/api/health`, 1 vCPU / 2 GB is sufficient.

   ```bash
   aws apprunner create-service \
     --service-name circuitsleuth \
     --source-configuration ImageRepository='{ImageRepositoryType=ECR,ImageIdentifier=<account>.dkr.ecr.<region>.amazonaws.com/circuitsleuth:latest,ImageConfiguration={Port=8080},ImageRepositoryCredentials={Credentials=<arn>}}' \
     --instance-configuration Cpu='1 vCPU',Memory='2 GB'
   ```

3. Attach an S3 bucket + instance role if you want run artifacts persisted outside
   the container: set `CIRCUITSLEUTH_DATA_DIR=/tmp/data` for ephemeral use today;
   moving `app/store.py` artifact storage onto `boto3` S3 is a contained change
   (single module) but was **not implemented or tested** here.

CloudWatch: App Runner streams container stdout to CloudWatch Logs by default;
the backend logs via uvicorn already.

## Configuration

All settings are environment-driven with the `CIRCUITSLEUTH_` prefix
(`backend/app/config.py`): data dir, budgets, detection thresholds, CORS origins,
upload limits.
