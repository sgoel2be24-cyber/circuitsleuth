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

    async def drive():
        import json
        # Real MCP dispatch creates a fresh toolbelt for every tool call.
        ctx = json.loads(await mcp_server.get_inspection_context("ins_mcptest"))
        assert ctx["inspection_id"] == "ins_mcptest"
        reg = json.loads(await mcp_server.align_images("ins_mcptest"))
        assert reg["ok"]
        det = json.loads(await mcp_server.detect_defects("ins_mcptest"))
        assert det["candidate_count"] >= 1
        rid = next(iter(det["candidates"]))
        view = json.loads(await mcp_server.request_additional_view("ins_mcptest", rid))
        assert view["status"] == "compared"
        verdict = json.loads(await mcp_server.verify_candidate("ins_mcptest", rid))
        assert verdict["verdict"] in ("CONFIRMED_DEFECT", "LIKELY_DEFECT")
        report = json.loads(await mcp_server.generate_inspection_report("ins_mcptest"))
        assert report["verdicts"]

    asyncio.run(drive())

    # state was persisted; an external MCP client in another process sees it
    persisted = store.load_state("ins_mcptest")
    assert persisted["status"] == "created"  # orchestrator never started; tools did
    assert persisted["candidates"]
    assert persisted["report"] is not None
    events = store.get_events("ins_mcptest")
    assert len(events) == len(persisted["events"])
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))


def test_unknown_inspection_raises():
    from app.tools.registry import ToolError
    from app.tools import mcp_server

    with pytest.raises(ToolError):
        mcp_server._bind("ins_does_not_exist")
