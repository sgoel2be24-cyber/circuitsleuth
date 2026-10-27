"""API tests via FastAPI TestClient (temp data dir per test session)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory, demo_dir, monkeypatch_module):
    from app.config import Settings
    import app.config as cfg
    import app.store as store

    data_dir = tmp_path_factory.mktemp("api-data")
    s = Settings(data_dir=data_dir)
    cfg.settings = s
    monkeypatch_module(cfg, "settings", s)
    monkeypatch_module(store, "settings", s)
    # copy demo scenarios into the temp data dir so demo endpoints work
    import shutil

    (data_dir / "demo").mkdir(exist_ok=True)
    shutil.copytree(demo_dir, data_dir / "demo", dirs_exist_ok=True)

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def monkeypatch_module():
    def _patch(module, name, value):
        setattr(module, name, value)

    return _patch


def test_health_and_system(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok"
    assert r["opencv_version"].startswith("5.")
    info = client.get("/api/system/info").json()
    assert info["opencv_version"].startswith("5.")
    assert "limits" in info


def test_demo_scenarios_listed(client):
    scenarios = client.get("/api/demo/scenarios").json()
    assert len(scenarios) == 6
    assert {s["id"] for s in scenarios} >= {"scenario_01_clear_defects"}


def _create_and_run(client, scenario: str, budget: int = 12) -> str:
    r = client.post("/api/inspections", data={"scenario_id": scenario, "max_tool_calls": budget})
    assert r.status_code == 200, r.text
    ins = r.json()
    iid = ins["id"]
    assert client.post(f"/api/inspections/{iid}/start").status_code == 200
    for _ in range(120):
        d = client.get(f"/api/inspections/{iid}").json()
        if d["status"] in ("completed", "failed"):
            return iid
        time.sleep(0.2)
    raise TimeoutError("inspection did not finish")


def test_full_inspection_journey(client):
    iid = _create_and_run(client, "scenario_01_clear_defects")
    d = client.get(f"/api/inspections/{iid}").json()
    assert d["status"] == "completed"
    assert d["summary"]["confirmed"] >= 1
    assert d["registration"]["quality"] == "good"
    assert d["coordinate_space"] == "reference"
    assert "aligned_test" in d["images"]
    assert client.get(d["images"]["aligned_test"]).status_code == 200
    assert d["candidates"]
    rid = next(iter(d["candidates"]))
    crop_dimensions = []
    import cv2
    import numpy as np

    for role in ("reference", "aligned_test", "difference"):
        response = client.get(f"/api/inspections/{iid}/candidates/{rid}/crop/{role}")
        assert response.status_code == 200 and response.headers["content-type"] == "image/png"
        crop_dimensions.append(cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR).shape)
    assert len(set(crop_dimensions)) == 1
    assert client.get(f"/api/inspections/{iid}/candidates/missing/crop/reference").status_code == 404
    assert client.get(f"/api/inspections/{iid}/candidates/{rid}/crop/unknown").status_code == 400
    # images and artifacts are served
    img = client.get(f"/api/inspections/{iid}/images/reference")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    art = client.get(f"/api/inspections/{iid}/artifacts/diff_heatmap")
    assert art.status_code == 200
    # report
    report = client.get(f"/api/inspections/{iid}/report").json()
    assert report["inspection_id"] == iid
    assert len(report["verdicts"]) == len(d["candidates"])
    assert report["limitations"]


def test_registration_failure_scenario_over_api(client):
    iid = _create_and_run(client, "scenario_04_registration_failure")
    d = client.get(f"/api/inspections/{iid}").json()
    assert d["stop_reason"] == "registration_failed"
    assert d["summary"]["confirmed"] == 0


def test_operator_review_endpoint(client):
    iid = _create_and_run(client, "scenario_05_no_second_view")
    d = client.get(f"/api/inspections/{iid}").json()
    rid = next(rid for rid, c in d["candidates"].items() if c["status"] == "NEEDS_REVIEW")
    r = client.post(f"/api/inspections/{iid}/review",
                    json={"region_id": rid, "decision": "confirmed", "note": "looks real"})
    assert r.status_code == 200
    d = client.get(f"/api/inspections/{iid}").json()
    assert d["candidates"][rid]["status"] == "CONFIRMED_DEFECT"
    assert "operator review" in d["candidates"][rid]["label_basis"]
    report = client.get(f"/api/inspections/{iid}/report").json()
    reviewed = next(v for v in report["verdicts"] if v["region_id"] == rid)
    assert reviewed["status"] == "CONFIRMED_DEFECT"
    assert "operator review" in reviewed["label_basis"]
    review_task = next(r for r in report["review_requests"] if r["region_id"] == rid)
    assert review_task["resolved"] == "confirmed"
    events = client.get(f"/api/inspections/{iid}/events/all").json()
    assert len({e["seq"] for e in events}) == len(events)
    assert any(e["type"] == "operator_review" for e in events)
    assert any(e["type"] == "report_ready" for e in events)


def test_reject_on_start_after_completion(client):
    iid = _create_and_run(client, "scenario_02_clean_board")
    r = client.post(f"/api/inspections/{iid}/start")
    assert r.status_code == 409


def test_upload_inspection_rejects_garbage(client):
    r = client.post(
        "/api/inspections",
        files={"reference": ("a.png", b"notanimage", "image/png"),
               "test": ("b.png", b"alsonot", "image/png")},
    )
    assert r.status_code == 400


def test_unknown_inspection_404(client):
    assert client.get("/api/inspections/ins_nope").status_code == 404
    assert client.get("/api/inspections/ins_nope/report").status_code == 404


@pytest.mark.parametrize("field,value", [("max_tool_calls", 0), ("max_tool_calls", 41),
                                         ("max_iterations", 1), ("max_iterations", 101)])
def test_invalid_budget_is_validation_error(client, field, value):
    response = client.post("/api/inspections", data={
        "scenario_id": "scenario_02_clean_board", field: value,
    })
    assert response.status_code == 422


def test_invalid_review_payload_is_validation_error(client):
    iid = _create_and_run(client, "scenario_01_clear_defects")
    assert client.post(f"/api/inspections/{iid}/review", json={
        "region_id": "R01", "decision": "confirmed", "note": {"bad": "type"},
    }).status_code == 422


def test_running_evidence_is_immutable_and_operator_can_abort(client, monkeypatch):
    import asyncio
    from app.api import routes

    async def stalled_run(state, sink):
        await asyncio.Event().wait()

    monkeypatch.setattr(routes.orchestrator, "run_inspection", stalled_run)
    iid = client.post("/api/inspections", data={
        "scenario_id": "scenario_01_clear_defects",
    }).json()["id"]
    assert client.post(f"/api/inspections/{iid}/start").status_code == 200
    assert client.get(f"/api/inspections/{iid}").json()["status"] == "running"
    assert client.post(f"/api/inspections/{iid}/start").status_code == 409
    assert client.post(f"/api/inspections/{iid}/rerun").status_code == 409
    assert client.post(f"/api/inspections/{iid}/views", files={
        "view2": ("new.png", b"not decoded because state is busy", "image/png"),
    }).status_code == 409
    assert client.post(f"/api/inspections/{iid}/abort").status_code == 200
    state = client.get(f"/api/inspections/{iid}").json()
    assert state["status"] == "failed"
    assert state["stop_reason"] == "operator_requested_termination"
    assert client.post(f"/api/inspections/{iid}/start").status_code == 409
    assert client.post(f"/api/inspections/{iid}/abort").status_code == 409


def test_upload_limit_checked_before_decode(client, monkeypatch):
    from app.api import routes
    monkeypatch.setattr(routes.settings, "max_upload_bytes", 16)
    response = client.post("/api/inspections", files={
        "reference": ("large.png", b"x" * 32, "image/png"),
        "test": ("test.png", b"x" * 32, "image/png"),
    })
    assert response.status_code == 413


def _audit_snapshot(ins_id):
    from app import store
    rdir = store.run_dir(ins_id)
    return {
        "files": {str(p.relative_to(rdir)): p.read_bytes() for p in rdir.rglob("*")
                  if p.is_file() and p.name != ".mutation.lock"},
        "row": dict(store.get_inspection_row(ins_id)),
        "events": store.get_events(ins_id),
    }


def test_capture_creates_audited_child_without_mutating_parent(client):
    import hashlib
    from app import store
    iid = _create_and_run(client, "scenario_05_no_second_view")
    before = _audit_snapshot(iid)
    image = client.get(f"/api/inspections/{iid}/images/test").content
    response = client.post(f"/api/inspections/{iid}/views", files={
        "view2": ("recapture.png", image, "image/png"),
    })
    assert response.status_code == 200, response.text
    child = response.json()["inspection_id"]
    assert child != iid
    for _ in range(100):
        d = client.get(f"/api/inspections/{child}").json()
        if d["status"] != "running":
            break
        time.sleep(.1)
    assert d["status"] == "completed"
    assert d["parent_inspection_id"] == iid
    assert "view2" in d["images"]
    for role, digest in d["input_hashes"].items():
        assert digest == hashlib.sha256((store.run_dir(child) / f"{role}.png").read_bytes()).hexdigest()
    events = client.get(f"/api/inspections/{child}/events/all").json()
    assert events[0]["type"] == "capture_attached"
    assert events[0]["evidence"]["input_hashes"] == d["input_hashes"]
    assert _audit_snapshot(iid) == before


def test_failed_capture_child_preserves_original(client, monkeypatch):
    from app.api import routes
    iid = _create_and_run(client, "scenario_05_no_second_view")
    before = _audit_snapshot(iid)
    image = client.get(f"/api/inspections/{iid}/images/test").content
    assert client.post(f"/api/inspections/{iid}/rerun", files={
        "view2": ("bad.png", b"bad", "image/png"),
    }).status_code == 400
    assert _audit_snapshot(iid) == before

    async def fail_start(ins_id):
        raise routes.HTTPException(503, "injected child start failure")

    monkeypatch.setattr(routes, "start_inspection", fail_start)
    response = client.post(f"/api/inspections/{iid}/rerun", files={
        "view2": ("recapture.png", image, "image/png"),
    })
    assert response.status_code == 503
    assert _audit_snapshot(iid) == before


def test_rejected_review_clears_final_label_everywhere(client):
    from app import store
    iid = _create_and_run(client, "scenario_01_clear_defects")
    rid = next(iter(client.get(f"/api/inspections/{iid}").json()["candidates"]))
    response = client.post(f"/api/inspections/{iid}/review", json={
        "region_id": rid, "decision": "rejected", "note": "Artifact confirmed by operator",
    })
    assert response.status_code == 200
    state = store.load_state(iid)
    view = client.get(f"/api/inspections/{iid}").json()
    report = client.get(f"/api/inspections/{iid}/report").json()
    for candidate in (state["candidates"][rid], view["candidates"][rid],
                      next(v for v in report["verdicts"] if v["region_id"] == rid)):
        assert candidate["status"] == "CLEARED"
        assert candidate["label"] is None
        assert candidate["label_basis"] == "operator review (rejected)"


def test_rest_mcp_ownership_and_terminal_contract(client):
    import asyncio
    from app import store
    from app.tools import mcp_server
    from app.tools.registry import ToolError
    iid = client.post("/api/inspections", data={"scenario_id": "scenario_01_clear_defects"}).json()["id"]
    asyncio.run(mcp_server.align_images(iid))
    assert client.get(f"/api/inspections/{iid}").json()["execution_mode"] == "mcp"
    assert client.post(f"/api/inspections/{iid}/start").status_code == 409
    asyncio.run(mcp_server.detect_defects(iid))
    asyncio.run(mcp_server.generate_inspection_report(iid))
    assert client.get(f"/api/inspections/{iid}").json()["status"] == "completed"
    before = _audit_snapshot(iid)
    with pytest.raises(ToolError):
        asyncio.run(mcp_server.detect_defects(iid))
    assert client.post(f"/api/inspections/{iid}/start").status_code == 409
    assert _audit_snapshot(iid) == before
    rest_id = _create_and_run(client, "scenario_01_clear_defects")
    before = _audit_snapshot(rest_id)
    with pytest.raises(ToolError):
        asyncio.run(mcp_server.align_images(rest_id))
    assert _audit_snapshot(rest_id) == before
    # The same per-run lock protects API and MCP writers, including the gap
    # between loading state and an awaited tool result.
    with store.mutation_lock(iid):
        assert client.post(f"/api/inspections/{iid}/rerun").status_code == 409
        with pytest.raises(ToolError, match="active writer"):
            asyncio.run(mcp_server.generate_inspection_report(iid))
