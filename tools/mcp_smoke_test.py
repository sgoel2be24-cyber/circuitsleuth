"""Live MCP stdio smoke test: spawn the real server, list tools, drive one.

Run:  .venv/Scripts/python.exe tools/mcp_smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


async def main() -> None:
    # 1. create a completed inspection via the REST API
    api = httpx.Client(base_url="http://127.0.0.1:8100", timeout=60)
    iid = api.post("/api/inspections", data={"scenario_id": "scenario_01_clear_defects"}).json()["id"]
    api.post(f"/api/inspections/{iid}/start")
    for _ in range(100):
        if api.get(f"/api/inspections/{iid}").json()["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.3)
    print(f"inspection {iid} ready")

    # 2. spawn the MCP server as a subprocess and speak real MCP over stdio
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    params = StdioServerParameters(
        command=py,
        args=[str(ROOT / "backend" / "app" / "tools" / "mcp_server.py")],
        env=None,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("MCP tools:", names)
            assert len(names) == 8, names

            ctx = await session.call_tool("get_inspection_context", {"inspection_id": iid})
            data = __import__("json").loads(ctx.content[0].text)
            assert data["inspection_id"] == iid
            assert data["available_views"]["secondary"] is True
            print("get_inspection_context ok:",
                  list(data["candidates"]), "| status:", data["status"])

            report = await session.call_tool("generate_inspection_report", {"inspection_id": iid})
            rep = __import__("json").loads(report.content[0].text)
            print("generate_inspection_report ok:", [v["status"] for v in rep["verdicts"]])
    print("MCP stdio smoke test PASSED")


if __name__ == "__main__":
    t0 = time.perf_counter()
    asyncio.run(main())
    print(f"({time.perf_counter() - t0:.1f}s)")
