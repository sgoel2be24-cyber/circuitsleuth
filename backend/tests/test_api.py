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
    assert d["candidates"]
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
