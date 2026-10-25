"""MCP server surface tests: tools registered, callable against real state."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

EXPECTED_TOOLS = {
    "get_inspection_context", "align_images", "detect_defects", "inspect_region",
    "request_additional_view", "verify_candidate", "request_human_review",
    "generate_inspection_report",
}


def test_all_spec_tools_registered():
    from app.tools import mcp_server

    registered = set(mcp_server.mcp._tool_manager._tools.keys())
    assert EXPECTED_TOOLS <= registered


def test_mcp_tools_operate_on_real_state(tmp_path, monkeypatch):
    """Drive a real inspection through the MCP tool functions (no API)."""
    from tests.conftest import make_state, write_scenario
    from app.tools import mcp_server
    import app.store as store

    monkeypatch.setattr(store, "settings", store.settings.__class__(data_dir=tmp_path))

    scenario_dir = tmp_path / "demo" / "scenario_01_clear_defects"
    write_scenario(tmp_path / "demo", "scenario_01_clear_defects")
    state = make_state(scenario_dir)
    state["id"] = "ins_mcptest"
    state["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    store.create_inspection(
        state["id"], source="demo", scenario_id="scenario_01_clear_defects",
        config=state["config"],
        summary={"id": state["id"], "created_at": state["created_at"], "status": "created",
                 "source": "demo", "scenario_id": "scenario_01_clear_defects",
                 "config": state["config"], "candidate_count": 0, "confirmed": 0,
                 "cleared": 0, "needs_review": 0, "not_evaluable": 0,
                 "tool_calls_used": 0, "duration_s": None},
    )
    store.save_state(state["id"], state)

    tb = mcp_server._bind("ins_mcptest")

    async def drive():
        ctx = await tb.get_inspection_context()
        assert ctx["inspection_id"] == "ins_mcptest"
        reg = await tb.align_images()
        assert reg["ok"]
        det = await tb.detect_defects()
        assert det["candidate_count"] >= 1
        rid = next(iter(det["candidates"]))
        view = await tb.request_additional_view(rid)
        assert view["status"] == "compared"
        verdict = await tb.verify_candidate(rid)
        assert verdict["verdict"] in ("CONFIRMED_DEFECT", "LIKELY_DEFECT")
        report = await tb.generate_inspection_report()
        assert report["verdicts"]

    asyncio.run(drive())

    # state was persisted; an external MCP client in another process sees it
    persisted = store.load_state("ins_mcptest")
    assert persisted["status"] == "created"  # orchestrator never started; tools did
    assert persisted["candidates"]
    assert persisted["report"] is not None


def test_unknown_inspection_raises():
    from app.tools.registry import ToolError
    from app.tools import mcp_server

    with pytest.raises(ToolError):
        mcp_server._bind("ins_does_not_exist")
