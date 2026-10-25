# CircuitSleuth — single-container build: FastAPI + OpenCV 5 backend, static React frontend.
# Build:  docker build -t circuitsleuth .
# Run:    docker run -p 8080:8080 circuitsleuth

# ---- frontend build stage ----
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime stage ----
FROM python:3.11-slim
WORKDIR /app

# opencv-python-headless needs libgl/glib even headless on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY tools/ tools/
COPY --from=frontend /app/dist frontend/dist/
# demo dataset is generated at container start if missing (deterministic seeds)

ENV CIRCUITSLEUTH_DATA_DIR=/app/data
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "python tools/generate_dataset.py --out data/demo; \
      uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
