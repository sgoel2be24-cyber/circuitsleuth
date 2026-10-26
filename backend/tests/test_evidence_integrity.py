"""Regressions for uncertainty, budgets and persisted audit integrity."""

import asyncio
import json
import sys
import threading

import pytest

from app.cv.verification import verify_candidate
from app.tools.registry import InspectionToolbelt
from app import store


def test_ledger_orders_same_second_runs_by_creation_and_keeps_limit(tmp_path, monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(store, "settings", Settings(data_dir=tmp_path))
    for iid, created in [("ins_old", "2026-10-26T12:00:00"),
                         ("ins_zzz", "2026-10-26T12:00:01"),
                         ("ins_aaa", "2026-10-26T12:00:01")]:
        store.create_inspection(iid, source="demo", scenario_id=None, config={},
                                summary={"id": iid, "created_at": created})
    # Updating an earlier run must not make it the latest-created inspection.
    store.update_inspection("ins_zzz", status="completed")
    assert [row["id"] for row in store.list_inspections()] == ["ins_aaa", "ins_zzz", "ins_old"]
    assert [row["id"] for row in store.list_inspections(limit=2)] == ["ins_aaa", "ins_zzz"]


def _candidate():
    return {
        "region_id": "R01", "bbox": [10, 10, 20, 20], "area_px": 100,
        "difference_score": 0.3, "structural_mismatch_score": 0.5,
        "evidence_quality_score": 0.8, "tools_used": [], "notes": [],
        "status": "SUSPECTED",
        "evidence": [
            {"evidence_kind": "difference_severity", "source_tool": "highres_zoom",
             "supports_defect": True, "metrics": {}},
            {"evidence_kind": "edge_topology", "source_tool": "edge_topology",
             "supports_defect": True, "metrics": {}},
        ],
    }


def test_unreliable_independent_view_cannot_be_overridden_by_reprocessing():
    candidate = _candidate()
    evidence = candidate["evidence"] + [{
        "evidence_kind": "independent_view", "source_tool": "alternate_view",
        "supports_defect": None, "metrics": {},
    }]
    verdict, *_ = verify_candidate(candidate, evidence, "good")
    assert verdict == "NEEDS_REVIEW"


def test_independent_view_confirmation_policy_is_enforced():
    candidate = _candidate()
    state = {
        "id": "test_policy", "registration": {"quality": "good"},
        "config": {"require_independent_view_for_confirm": True},
        "candidates": {"R01": candidate}, "events": [],
    }
    result = asyncio.run(InspectionToolbelt(state, persist=False).verify_candidate("R01"))
    assert result["verdict"] == "LIKELY_DEFECT"
    assert any("requires an independent view" in note for note in result["notes"])


def test_missing_view_request_respects_tool_budget():
    state = {
        "id": "test_budget", "config": {"max_tool_calls": 3},
        "tool_calls_used": 3, "images": {"view2": None},
        "candidates": {"R01": _candidate()}, "events": [],
    }
    result = asyncio.run(InspectionToolbelt(state, persist=False).request_additional_view("R01"))
    assert not result["ok"] and result["status"] == "budget_exhausted"
    assert state["tool_calls_used"] == 3


@pytest.mark.parametrize("identifier", ["../outside", "..\\outside", "C:\\outside", ""])
def test_persisted_inspection_lookup_rejects_paths(identifier):
    with pytest.raises(ValueError, match="identifier"):
        store.load_state(identifier)


def test_opencv4_runtime_is_rejected(monkeypatch):
    from app.api import routes
    monkeypatch.setattr(routes.cv2, "__version__", "4.99.0")
    with pytest.raises(RuntimeError, match="requires OpenCV 5"):
        asyncio.run(routes._sweep_interrupted_runs())


def test_cancelled_orchestrator_persists_honest_terminal_state(tmp_path, monkeypatch):
    from app.agent.orchestrator import run_inspection
    monkeypatch.setattr(store, "settings", store.settings.__class__(data_dir=tmp_path))

    async def waiting_alignment(self, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(InspectionToolbelt, "align_images", waiting_alignment)
    state = {
        "id": "test_cancel", "created_at": "2026-10-25T00:00:00", "source": "upload",
        "status": "created", "images": {"reference": "ref", "test": "test", "view2": None},
        "config": {"max_tool_calls": 3, "max_iterations": 5},
        "candidates": {"R01": _candidate()}, "events": [], "tool_calls_used": 0,
        "iterations": 0, "review_requests": [],
    }

    async def cancel():
        task = asyncio.create_task(run_inspection(state))
        await asyncio.sleep(0)
        task.cancel()
        return await task

    result = asyncio.run(cancel())
    assert result["status"] == "failed"
    assert result["stop_reason"] == "operator_requested_termination"
    assert result["candidates"]["R01"]["status"] == "NEEDS_REVIEW"
    persisted = store.load_state(state["id"])
    assert persisted["review_requests"]
    assert persisted["events"][-1]["type"] == "inspection_aborted"


def test_spa_deep_links_load_shell_without_hiding_missing_resources(tmp_path):
    from fastapi.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from app.main import FrontendFiles

    (tmp_path / "index.html").write_text("<html>CircuitSleuth shell</html>")
    application = Starlette(routes=[Mount("/", FrontendFiles(directory=tmp_path, html=True))])
    with TestClient(application) as client:
        deep = client.get("/inspections/ins_example")
        assert deep.status_code == 200 and "CircuitSleuth shell" in deep.text
        assert client.get("/api/missing").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/missing.png").status_code == 404


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file-sharing semantics")
def test_atomic_state_save_retries_a_brief_windows_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "settings", store.settings.__class__(data_dir=tmp_path))
    path = store.save_state("test_reader", {"value": "old"})
    reader = path.open("r")
    release = threading.Timer(0.05, reader.close)
    release.start()
    try:
        store.save_state("test_reader", {"value": "new"})
    finally:
        release.join()
        reader.close()
    assert json.loads(path.read_text()) == {"value": "new"}
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file-sharing semantics")
def test_atomic_state_save_preserves_old_file_when_reader_stays_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "settings", store.settings.__class__(data_dir=tmp_path))
    path = store.save_state("test_denial", {"value": "old"})
    monkeypatch.setattr(store.time, "sleep", lambda delay: None)
    with path.open("r"):
        with pytest.raises(PermissionError):
            store.save_state("test_denial", {"value": "new"})
    assert json.loads(path.read_text()) == {"value": "old"}
    assert not list(path.parent.glob("*.tmp"))
