"""Isolated synthetic-only demo gateway; pair with a temporary HTTPS tunnel.

No normal local/AWS routes or stores are changed. Keep the demo host online.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "scenario_01_clear_defects", "scenario_02_clean_board", "scenario_03_ambiguous_glare",
    "scenario_04_registration_failure", "scenario_05_no_second_view", "scenario_06_multiple_regions",
}


class PublicDemoGuard(BaseHTTPMiddleware):
    def __init__(self, app, *, count_runs, active_runs, max_runs=100):
        super().__init__(app)
        self.count_runs, self.active_runs, self.max_runs = count_runs, active_runs, max_runs
        self.writers = asyncio.Lock()
        self.recent = deque()

    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method in {"GET", "HEAD"}:
            # Quick Tunnels do not support SSE; the UI already polls events.
            if re.fullmatch(r"/api/inspections/ins_[a-zA-Z0-9_-]+/events", path):
                return JSONResponse({"detail": "Public demo uses event polling"}, status_code=404)
            response = await call_next(request)
            if request.method == "GET" and path == "/api/health" and response.status_code == 200:
                data = json.loads(b"".join([part async for part in response.body_iterator]))
                return JSONResponse({**data, "public_demo": True})
            return response
        if request.method != "POST" or not re.fullmatch(
            r"/api/inspections(?:/ins_[a-zA-Z0-9_-]+/(?:start|rerun|abort|review))?", path
        ):
            return JSONResponse({"detail": "Unavailable in this public demonstration"}, status_code=403)
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            size = -1
        if not 0 <= size <= 8192:
            return JSONResponse({"detail": "Public demo requests must have a length below 8 KB"}, status_code=413)
        # Proxies may omit Content-Length on an empty POST or stream a body.
        # Read with an actual byte bound, then cache it for Starlette's
        # _CachedRequest.wrapped_receive and the downstream FastAPI parser.
        chunks, received = [], 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > 8192:
                return JSONResponse({"detail": "Public demo request exceeds 8 KB"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
        creates_run = path == "/api/inspections" or path.endswith("/rerun")
        if creates_run:
            form = await request.form()
            if any(hasattr(value, "filename") for _, value in form.multi_items()):
                return JSONResponse({"detail": "Public demo accepts synthetic scenarios only; personal uploads are disabled"}, status_code=403)
            if set(form) - {"scenario_id", "max_tool_calls", "max_iterations"}:
                return JSONResponse({"detail": "Unsupported public demo input"}, status_code=403)
            if path == "/api/inspections":
                if form.get("scenario_id") not in SCENARIOS:
                    return JSONResponse({"detail": "Select a bundled synthetic scenario"}, status_code=403)
                try:
                    valid = 1 <= int(form.get("max_tool_calls", 12)) <= 12 and 2 <= int(form.get("max_iterations", 24)) <= 24
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    return JSONResponse({"detail": "Public demo allows at most 12 tool calls and 24 iterations"}, status_code=422)
        async with self.writers:
            now = time.monotonic()
            while self.recent and self.recent[0] < now - 60:
                self.recent.popleft()
            if len(self.recent) >= 60 or ((creates_run or path.endswith("/start")) and self.active_runs() >= 2):
                return JSONResponse({"detail": "Demo is busy; retry after an inspection finishes"}, status_code=429)
            if creates_run and self.count_runs() >= self.max_runs:
                return JSONResponse({"detail": "This temporary demo session has reached its run limit"}, status_code=429)
            self.recent.append(now)
            return await call_next(request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8101)
    args = parser.parse_args()
    data = args.data_dir.resolve()
    if data == ROOT or data.is_relative_to(ROOT):
        parser.error("use a separate disposable directory outside the checkout")
    marker = data / ".public-demo-store"
    if data.exists() and any(data.iterdir()) and not marker.exists():
        parser.error("refusing to expose an existing non-demo data directory")
    data.mkdir(parents=True, exist_ok=True)
    marker.touch()
    shutil.copytree(ROOT / "data/demo", data / "demo", dirs_exist_ok=True)
    os.environ["CIRCUITSLEUTH_DATA_DIR"] = str(data)
    sys.path.insert(0, str(ROOT / "backend"))
    from app.main import app
    from app import store
    from app.api.routes import _running_tasks
    import uvicorn
    app.add_middleware(PublicDemoGuard, count_runs=lambda: len(store.list_inspections(limit=100)),
                       active_runs=lambda: sum(not task.done() for task in _running_tasks.values()))
    uvicorn.run(app, host="127.0.0.1", port=args.port, http="h11", ws="none")


if __name__ == "__main__":
    main()
