"""ASGI entrypoint: uvicorn backend.app.main:app

In containerized deployments the built frontend (frontend/dist) is served as
static files by this same process, so a single container exposes both the API
and the UI.
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from .api.routes import app  # noqa: F401

_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
