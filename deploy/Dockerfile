# CircuitSleuth — single-container build: FastAPI + OpenCV 5 backend, static React frontend.
# Build:  docker build -f deploy/Dockerfile -t circuitsleuth .
# Run:    docker run -p 8080:8080 circuitsleuth

# ---- frontend build stage ----
FROM node:24-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime stage ----
FROM python:3.13-slim
WORKDIR /app

# Runtime libraries for the bundled OpenCV wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.lock.txt backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt && pip check

COPY backend/ backend/
COPY tools/ tools/
COPY --from=frontend /app/dist frontend/dist/
# demo dataset is generated at container start if missing (deterministic seeds)

ENV CIRCUITSLEUTH_DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "python tools/generate_dataset.py --out \"${CIRCUITSLEUTH_DATA_DIR}/demo\" && \
      exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --http h11 --ws none"]
