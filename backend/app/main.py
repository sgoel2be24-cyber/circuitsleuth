"""ASGI entrypoint: uvicorn backend.app.main:app

In containerized deployments the built frontend (frontend/dist) is served as
static files by this same process, so a single container exposes both the API
and the UI.
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .api.routes import app  # noqa: F401

_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class FrontendFiles(StaticFiles):
    """Resolve browser routes to the SPA shell without hiding missing APIs/assets."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            relative = path.replace("\\", "/").lstrip("/")
            if (exc.status_code == 404 and not relative.startswith(("api/", "assets/"))
                    and "." not in Path(path).name):
                return await super().get_response("index.html", scope)
            raise


if _DIST.exists():
    app.mount("/", FrontendFiles(directory=str(_DIST), html=True), name="frontend")
