"""CircuitSleuth FastAPI application."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .. import store
from ..agent import orchestrator
from ..config import settings
from ..schemas import InspectionConfig
from ..tools.registry import ToolError
from .. import __version__

app = FastAPI(title="CircuitSleuth API", version=__version__)


@app.on_event("startup")
async def _sweep_interrupted_runs() -> None:
    """Mark runs left 'running' by a process restart as failed, honestly."""
    if not settings.runs_dir.exists():
        return
    for state_path in settings.runs_dir.glob("*/state.json"):
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if state.get("status") != "running":
            continue
        state["status"] = "failed"
        state["stop_reason"] = "interrupted by backend restart"
        state_path.write_text(json.dumps(state, indent=1, default=str))
        row = store.get_inspection_row(state["id"])
        if row:
            summary = json.loads(row["summary"])
            summary["status"] = "failed"
            summary["stop_reason"] = state["stop_reason"]
            store.update_inspection(state["id"], status="failed", summary=summary)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# live SSE subscribers per inspection
_subscribers: dict[str, set[asyncio.Queue]] = {}
_running_tasks: dict[str, asyncio.Task] = {}


def _http(ins_id: str) -> None:
    row = store.get_inspection_row(ins_id)
    if row is None:
        raise HTTPException(404, f"unknown inspection {ins_id!r}")


async def _broadcast(ins_id: str, event: dict) -> None:
    for q in list(_subscribers.get(ins_id, ())):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "opencv_version": cv2.__version__, "version": __version__}


@app.get("/api/system/info")
async def system_info() -> dict:
    return {
        "app": settings.app_name,
        "version": __version__,
        "opencv_version": cv2.__version__,
        "numpy_version": __import__("numpy").__version__,
        "python_version": __import__("sys").version.split()[0],
        "limits": {
            "max_upload_bytes": settings.max_upload_bytes,
            "max_image_dim_px": settings.max_image_dim_px,
        },
        "aws_execution_verified": False,
        "notes": "Local execution mode: core OpenCV processing runs in this process.",
    }


# --------------------------------------------------------------------- demo


@app.get("/api/demo/scenarios")
async def demo_scenarios() -> list[dict]:
    out = []
    for d in sorted(settings.demo_dir.glob("scenario_*")):
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        meta["files"] = {
            p.stem: str(p.name) for p in d.glob("*.png")
        }
        out.append(meta)
    return out


@app.get("/api/demo/scenarios/{scenario_id}/images/{which}")
async def demo_scenario_image(scenario_id: str, which: str):
    """Thumbnail image for the scenario picker."""
    if which not in ("reference", "test", "view2"):
        raise HTTPException(400, "unknown image role")
    p = settings.demo_dir / scenario_id / f"{which}.png"
    if not p.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(p, media_type="image/png")


@app.post("/api/inspections/{ins_id}/rerun")
async def rerun_inspection(ins_id: str) -> dict:
    """Clone an inspection's images (reference/test/view2) into a NEW inspection
    and start it immediately. Used after an operator supplies a missing
    secondary view, so the agent can re-inspect with the added evidence."""
    _http(ins_id)
    old_state = store.load_state(ins_id)
    if old_state is None:
        raise HTTPException(404, "state missing")
    src_dir = settings.runs_dir / ins_id
    new_state = {
        "id": store.new_id(),
        "created_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "created",
        "source": old_state["source"],
        "scenario_id": old_state.get("scenario_id"),
        "config": old_state["config"],
        "images": {},
        "candidates": {},
        "tool_calls_used": 0,
        "iterations": 0,
        "review_requests": [],
        "events": [],
    }
    rdir = store.run_dir(new_state["id"])
    for role in ("reference", "test", "view2"):
        src = src_dir / f"{role}.png"
        if src.exists():
            shutil.copyfile(src, rdir / f"{role}.png")
            new_state["images"][role] = str(rdir / f"{role}.png")
    new_state["images"].setdefault("view2", None)
    summary = {
        "id": new_state["id"], "created_at": new_state["created_at"], "status": "created",
        "source": new_state["source"], "scenario_id": new_state.get("scenario_id"),
        "config": new_state["config"], "candidate_count": 0, "confirmed": 0,
        "cleared": 0, "needs_review": 0, "not_evaluable": 0,
        "tool_calls_used": 0, "duration_s": None,
    }
    store.create_inspection(new_state["id"], source=new_state["source"],
                            scenario_id=new_state.get("scenario_id"),
                            config=new_state["config"], summary=summary)
    store.save_state(new_state["id"], new_state)
    await start_inspection(new_state["id"])
    return {"ok": True, "inspection_id": new_state["id"]}


# ------------------------------------------------------------- inspections


@app.get("/api/inspections")
async def list_inspections() -> list[dict]:
    return store.list_inspections()


@app.post("/api/inspections")
async def create_inspection(
    reference: UploadFile | None = File(None),
    test: UploadFile | None = File(None),
    view2: UploadFile | None = File(None),
    scenario_id: str | None = Form(None),
    max_tool_calls: int = Form(12),
    max_iterations: int = Form(24),
) -> dict:
    cfg = InspectionConfig(max_tool_calls=max_tool_calls, max_iterations=max_iterations)
    ins_id = store.new_id()
    rdir = store.run_dir(ins_id)

    def _check_ext(name: str) -> None:
        if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
            raise HTTPException(400, f"unsupported file type: {name}")

    if scenario_id:
        demo = settings.demo_dir / scenario_id
        if not (demo / "meta.json").exists():
            raise HTTPException(404, f"unknown demo scenario {scenario_id!r}")
        for src, dst in [("reference.png", "reference.png"), ("test.png", "test.png")]:
            shutil.copyfile(demo / src, rdir / dst)
        if (demo / "view2.png").exists():
            shutil.copyfile(demo / "view2.png", rdir / "view2.png")
        source = "demo"
    else:
        if reference is None or test is None:
            raise HTTPException(400, "reference and test images are required")
        for f, name in ((reference, "reference"), (test, "test"), (view2, "view2")):
            if f is None:
                continue
            _check_ext(f.filename or "")
            data = await f.read()
            from ..cv.imaging import decode_bgr, save_png

            try:
                img = decode_bgr(data, f.filename or name)
            except ValueError as exc:
                raise HTTPException(400, str(exc))
            save_png(img, rdir / f"{name}.png")
        source = "upload"

    created = __import__("time").strftime("%Y-%m-%dT%H:%M:%S")
    images = {
        "reference": str(rdir / "reference.png"),
        "test": str(rdir / "test.png"),
        "view2": str(rdir / "view2.png") if (rdir / "view2.png").exists() else None,
    }
    state = {
        "id": ins_id,
        "created_at": created,
        "status": "created",
        "source": source,
        "scenario_id": scenario_id,
        "config": cfg.model_dump(),
        "images": images,
        "candidates": {},
        "tool_calls_used": 0,
        "iterations": 0,
        "review_requests": [],
        "events": [],
    }
    summary = {
        "id": ins_id, "created_at": created, "status": "created", "source": source,
        "scenario_id": scenario_id, "config": cfg.model_dump(), "candidate_count": 0,
        "confirmed": 0, "cleared": 0, "needs_review": 0, "not_evaluable": 0,
        "tool_calls_used": 0, "duration_s": None,
    }
    store.create_inspection(ins_id, source=source, scenario_id=scenario_id,
                            config=cfg.model_dump(), summary=summary)
    store.save_state(ins_id, state)
    return summary


@app.post("/api/inspections/{ins_id}/start")
async def start_inspection(ins_id: str) -> dict:
    _http(ins_id)
    if ins_id in _running_tasks and not _running_tasks[ins_id].done():
        raise HTTPException(409, "inspection already running")
    state = store.load_state(ins_id)
    if state is None:
        raise HTTPException(404, "inspection state missing")
    if state.get("status") == "completed":
        raise HTTPException(409, "inspection already completed")
    store.update_inspection(ins_id, status="running")

    async def _sink(ev: dict) -> None:
        await _broadcast(ins_id, ev)

    task = asyncio.create_task(orchestrator.run_inspection(state, _sink))
    _running_tasks[ins_id] = task
    return {"ok": True, "inspection_id": ins_id}


@app.get("/api/inspections/{ins_id}")
async def get_inspection(ins_id: str) -> dict:
    _http(ins_id)
    state = store.load_state(ins_id)
    row = store.get_inspection_row(ins_id)
    summary = json.loads(row["summary"]) if row else None
    if state is None:
        raise HTTPException(404, "state missing")
    images = {
        k: f"/api/inspections/{ins_id}/images/{k}"
        for k in ("reference", "test", "view2") if state["images"].get(k)
    }
    return {
        "summary": summary,
        "status": state.get("status"),
        "config": state.get("config"),
        "registration": state.get("registration"),
        "detection": state.get("detection"),
        "candidates": state.get("candidates", {}),
        "review_requests": state.get("review_requests", []),
        "report": state.get("report"),
        "stop_reason": state.get("stop_reason"),
        "tool_calls_used": state.get("tool_calls_used", 0),
        "iterations": state.get("iterations", 0),
        "images": images,
    }


@app.get("/api/inspections/{ins_id}/events/all")
async def all_events(ins_id: str) -> list[dict]:
    """JSON snapshot of the event log (the /events route is an SSE stream)."""
    _http(ins_id)
    return store.get_events(ins_id)


@app.get("/api/inspections/{ins_id}/events")
async def stream_events(ins_id: str) -> StreamingResponse:
    _http(ins_id)
    past = store.get_events(ins_id)
    q: asyncio.Queue = asyncio.Queue(maxsize=512)
    _subscribers.setdefault(ins_id, set()).add(q)

    async def gen():
        try:
            for ev in past:
                yield f"data: {json.dumps(ev)}\n\n"
            state = store.load_state(ins_id)
            if state and state.get("status") in ("completed", "failed"):
                yield "event: done\ndata: {}\n\n"
                return
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(ev)}\n\n"
                if ev.get("type") in ("report_ready", "inspection_failed", "inspection_aborted"):
                    yield "event: done\ndata: {}\n\n"
                    return
        finally:
            _subscribers.get(ins_id, set()).discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.get("/api/inspections/{ins_id}/candidates")
async def get_candidates(ins_id: str) -> dict:
    _http(ins_id)
    state = store.load_state(ins_id)
    if state is None:
        raise HTTPException(404, "state missing")
    return {"candidates": state.get("candidates", {})}


@app.get("/api/inspections/{ins_id}/artifacts/{name}")
async def get_artifact(ins_id: str, name: str) -> FileResponse:
    _http(ins_id)
    p = store.artifact_path(ins_id, name)
    if p is None:
        raise HTTPException(404, "artifact not found")
    return FileResponse(p, media_type="image/png")


@app.get("/api/inspections/{ins_id}/images/{which}")
async def get_image(ins_id: str, which: str) -> FileResponse:
    _http(ins_id)
    if which not in ("reference", "test", "view2"):
        raise HTTPException(400, "unknown image role")
    p = settings.runs_dir / ins_id / f"{which}.png"
    if not p.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(p, media_type="image/png")


@app.post("/api/inspections/{ins_id}/views")
async def add_view(ins_id: str, view2: UploadFile = File(...)) -> dict:
    """Operator supplies a genuinely new capture for the inspection."""
    _http(ins_id)
    state = store.load_state(ins_id)
    if state is None:
        raise HTTPException(404, "state missing")
    data = await view2.read()
    from ..cv.imaging import decode_bgr, save_png

    try:
        img = decode_bgr(data, view2.filename or "view2")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    save_png(img, store.run_dir(ins_id) / "view2.png")
    state["images"]["view2"] = str(store.run_dir(ins_id) / "view2.png")
    store.save_state(ins_id, state)
    return {"ok": True}


@app.post("/api/inspections/{ins_id}/review")
async def submit_review(ins_id: str, payload: dict) -> dict:
    """Operator review decision for a region: {region_id, decision: confirmed|rejected, note?}."""
    _http(ins_id)
    state = store.load_state(ins_id)
    if state is None:
        raise HTTPException(404, "state missing")
    rid = payload.get("region_id")
    decision = payload.get("decision")
    if rid not in state.get("candidates", {}):
        raise HTTPException(404, f"unknown region {rid!r}")
    if decision not in ("confirmed", "rejected"):
        raise HTTPException(400, "decision must be 'confirmed' or 'rejected'")
    cand = state["candidates"][rid]
    cand["status"] = "CONFIRMED_DEFECT" if decision == "confirmed" else "CLEARED"
    cand["label_basis"] = f"operator review ({decision})"
    note = payload.get("note", "")
    if note:
        cand["notes"].append(f"operator note: {note}")
    state.setdefault("review_requests", [])
    for r in state["review_requests"]:
        if r.get("region_id") == rid:
            r["resolved"] = decision
    # append a synthetic event so the audit trail reflects the human decision
    ev = {
        "seq": (state["events"][-1]["seq"] + 1) if state.get("events") else 1,
        "ts": __import__("time").time(),
        "phase": "DECIDE",
        "type": "operator_review",
        "message": f"Operator {decision} region {rid}" + (f": {note}" if note else ""),
        "evidence": {"region_id": rid, "decision": decision, "note": note},
        "region_id": rid,
        "artifacts": [],
    }
    state["events"].append(ev)
    store.append_event(ins_id, ev)
    store.save_state(ins_id, state)
    _sync_summary_from_state(ins_id, state)
    await _broadcast(ins_id, ev)
    return {"ok": True}


def _sync_summary_from_state(ins_id: str, state: dict) -> None:
    v: dict[str, int] = {}
    for c in state.get("candidates", {}).values():
        v[c["status"]] = v.get(c["status"], 0) + 1
    row = store.get_inspection_row(ins_id)
    if not row:
        return
    summary = json.loads(row["summary"])
    summary.update({
        "status": state.get("status", "completed"),
        "candidate_count": len(state.get("candidates", {})),
        "confirmed": v.get("CONFIRMED_DEFECT", 0),
        "likely": v.get("LIKELY_DEFECT", 0),
        "cleared": v.get("CLEARED", 0),
        "needs_review": v.get("NEEDS_REVIEW", 0),
        "not_evaluable": v.get("NOT_EVALUABLE", 0),
        "tool_calls_used": state.get("tool_calls_used", 0),
        "duration_s": state.get("duration_s"),
        "stop_reason": state.get("stop_reason"),
    })
    store.update_inspection(ins_id, summary=summary, report=state.get("report"))


@app.get("/api/inspections/{ins_id}/report")
async def get_report(ins_id: str) -> dict:
    _http(ins_id)
    state = store.load_state(ins_id)
    if state is None:
        raise HTTPException(404, "state missing")
    report = state.get("report")
    if report is None:
        raise HTTPException(404, "report not generated yet")
    return report
