"""The optional public gateway must not expose uploads or unbounded work."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tools.public_demo import PublicDemoGuard


@pytest.fixture
def guarded():
    counters = {"runs": 0, "active": 0}
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "opencv_version": "5.0.0"}

    @app.post("/api/inspections")
    async def create(request: Request):
        # Ensure middleware validation leaves the real endpoint's body intact.
        return dict(await request.form())

    @app.post("/api/inspections/ins_example/abort")
    async def abort():
        return {"ok": True}

    app.add_middleware(PublicDemoGuard, count_runs=lambda: counters["runs"],
                       active_runs=lambda: counters["active"], max_runs=2)
    with TestClient(app) as client:
        yield client, counters


def test_synthetic_form_and_health_reach_app(guarded):
    client, _ = guarded
    assert client.get("/api/health").json()["public_demo"] is True
    response = client.post("/api/inspections", data={"scenario_id": "scenario_01_clear_defects", "max_tool_calls": 7})
    assert response.status_code == 200
    assert response.json()["max_tool_calls"] == "7"


@pytest.mark.parametrize("data,status", [
    ({"scenario_id": "../../private"}, 403),
    ({"scenario_id": "scenario_01_clear_defects", "max_tool_calls": 13}, 422),
    ({"scenario_id": "scenario_01_clear_defects", "max_iterations": 99}, 422),
    ({"scenario_id": "scenario_01_clear_defects", "reference": "private.png"}, 403),
])
def test_unknown_inputs_and_expensive_budgets_refused(guarded, data, status):
    client, _ = guarded
    assert client.post("/api/inspections", data=data).status_code == status


def test_upload_and_capture_bypasses_refused(guarded):
    client, _ = guarded
    assert client.post("/api/inspections", files={"reference": ("secret.png", b"private")}).status_code == 403
    assert client.post("/api/inspections/ins_example/rerun", files={"view2": ("secret.png", b"private")}).status_code == 403
    assert client.post("/api/inspections/ins_example/views", files={"view2": ("secret.png", b"private")}).status_code == 403
    assert client.post("/api/inspections", content=b"x" * 9000).status_code == 413


def test_capacity_refuses_new_work_but_allows_stop(guarded):
    client, counters = guarded
    counters["active"] = 2
    assert client.post("/api/inspections", data={"scenario_id": "scenario_01_clear_defects"}).status_code == 429
    assert client.post("/api/inspections/ins_example/abort").status_code == 200
    counters.update(active=0, runs=2)
    assert client.post("/api/inspections", data={"scenario_id": "scenario_01_clear_defects"}).status_code == 429


def test_proxy_empty_post_and_chunked_body_have_real_byte_bound(guarded):
    client, _ = guarded
    assert client.post("/api/inspections/ins_example/abort", content=iter([b""])).status_code == 200
    response = client.post("/api/inspections", content=iter([b"x" * 5000, b"y" * 4000]))
    assert response.status_code == 413
