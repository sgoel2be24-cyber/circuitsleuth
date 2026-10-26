"""Drive all eight tools over real MCP stdio with isolated synthetic data.

Run: .venv/Scripts/python.exe tools/mcp_smoke_test.py
No REST API is required. Existing inspection history is untouched.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from tools.generate_dataset import write_scenario  # noqa: E402


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="circuitsleuth-mcp-") as temporary:
        data = Path(temporary)
        scenario = "scenario_01_clear_defects"
        write_scenario(data / "demo", scenario)
        source = data / "demo" / scenario
        iid = "ins_mcp_smoke"
        run_dir = data / "runs" / iid
        run_dir.mkdir(parents=True)
        state = {
            "id": iid, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "created", "source": "demo", "scenario_id": scenario,
            "config": {"max_tool_calls": 12, "max_iterations": 24,
                       "require_independent_view_for_confirm": False},
            "images": {role: str(source / f"{role}.png")
                       for role in ("reference", "test", "view2")},
            "candidates": {}, "tool_calls_used": 0, "iterations": 0,
            "review_requests": [], "events": [],
        }
        (run_dir / "state.json").write_text(json.dumps(state))
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "backend" / "app" / "tools" / "mcp_server.py")],
            env={**os.environ, "CIRCUITSLEUTH_DATA_DIR": str(data)},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = sorted(t.name for t in (await session.list_tools()).tools)
                assert len(names) == 8, names
                print("MCP tools:", names)

                async def call(name: str, **arguments):
                    result = await session.call_tool(name, {"inspection_id": iid, **arguments})
                    assert not result.is_error, result
                    return json.loads(result.content[0].text)

                context = await call("get_inspection_context")
                assert context["available_views"]["secondary"]
                assert (await call("align_images"))["ok"]
                detection = await call("detect_defects")
                assert detection["candidate_count"] >= 2
                regions = list(detection["candidates"])
                rid = regions[0]
                assert (await call("inspect_region", region_id=rid, tool="highres_zoom"))["ok"]
                assert (await call("request_additional_view", region_id=rid))["status"] == "compared"
                verdict = await call("verify_candidate", region_id=rid)
                assert verdict["verdict"] in ("CONFIRMED_DEFECT", "LIKELY_DEFECT")
                assert (await call("request_human_review", region_id=regions[1],
                                  reason="MCP integration test operator task"))["ok"]
                report = await call("generate_inspection_report")
                assert len(report["verdicts"]) == detection["candidate_count"]
                assert report["review_requests"]
                print("All eight tools executed; verified verdict:", verdict["verdict"])

        persisted = json.loads((run_dir / "state.json").read_text())
        seq = [event["seq"] for event in persisted["events"]]
        assert seq == list(range(1, len(seq) + 1)), seq
        print(f"MCP stdio smoke test PASSED ({len(seq)} consecutive persisted audit events)")


if __name__ == "__main__":
    started = time.perf_counter()
    asyncio.run(main())
    print(f"({time.perf_counter() - started:.1f}s)")
