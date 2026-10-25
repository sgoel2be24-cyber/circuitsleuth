"""MCP server exposing CircuitSleuth's inspection tools over the Model
Context Protocol (stdio transport).

The tools are the *same* implementations the orchestrator uses internally
(`app.tools.registry.InspectionToolbelt`) — the server binds them to a
persisted inspection id, so an external MCP client (Claude Desktop, MCP
Inspector, or any SDK client) can drive or observe a real inspection.

Run:  python backend/app/tools/mcp_server.py
Config example (mcp_config.json in repo root):
{
  "mcpServers": {
    "circuitsleuth": {
      "command": "<path-to>/.venv/Scripts/python.exe",
      "args": ["backend/app/tools/mcp_server.py"]
    }
  }
}
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app import store  # noqa: E402
from app.tools.registry import InspectionToolbelt, ToolError  # noqa: E402

mcp = MCPServer("circuitsleuth")


def _bind(inspection_id: str) -> InspectionToolbelt:
    state = store.load_state(inspection_id)
    if state is None:
        raise ToolError(f"unknown inspection {inspection_id!r}")
    if state.get("status") == "running":
        raise ToolError("inspection is currently running in the API process; retry later")
    return InspectionToolbelt(state, None, persist=True)


@mcp.tool()
async def get_inspection_context(inspection_id: str) -> str:
    """Return the current inspection state: registration metrics, detected
    candidates with their evidence, available views and remaining budget."""
    return json.dumps(await _bind(inspection_id).get_inspection_context())


@mcp.tool()
async def align_images(inspection_id: str, recovery: bool = False) -> str:
    """Align the test image to the reference image (SIFT/ORB + RANSAC + ECC).
    Pass recovery=true to retry with CLAHE-enhanced preprocessing after a
    failure. Returns registration metrics and quality."""
    return json.dumps(await _bind(inspection_id).align_images(recovery=recovery))


@mcp.tool()
async def detect_defects(inspection_id: str) -> str:
    """Run OpenCV anomaly detection on the aligned pair; returns candidate
    regions with difference/structural-mismatch/quality scores."""
    return json.dumps(await _bind(inspection_id).detect_defects())


@mcp.tool()
async def inspect_region(inspection_id: str, region_id: str, tool: str) -> str:
    """Run a secondary analysis on a candidate region. tool is one of:
    highres_zoom, edge_topology, adaptive_threshold, local_realignment,
    alternate_view, request_capture."""
    return json.dumps(await _bind(inspection_id).inspect_region(region_id, tool))


@mcp.tool()
async def request_additional_view(inspection_id: str, region_id: str) -> str:
    """Consult the secondary captured view for a region, or return an
    explicit additional-capture-required status when none exists."""
    return json.dumps(await _bind(inspection_id).request_additional_view(region_id))


@mcp.tool()
async def verify_candidate(inspection_id: str, region_id: str) -> str:
    """Combine all evidence for a region into a final verdict
    (CONFIRMED_DEFECT / LIKELY_DEFECT / CLEARED / NEEDS_REVIEW / NOT_EVALUABLE)."""
    return json.dumps(await _bind(inspection_id).verify_candidate(region_id))


@mcp.tool()
async def request_human_review(inspection_id: str, region_id: str, reason: str,
                               requested_action: str = "operator confirmation") -> str:
    """Create a human review task for an uncertain region."""
    return json.dumps(
        await _bind(inspection_id).request_human_review(region_id, reason, requested_action)
    )


@mcp.tool()
async def generate_inspection_report(inspection_id: str) -> str:
    """Produce the structured final inspection report."""
    return json.dumps(await _bind(inspection_id).generate_inspection_report())


if __name__ == "__main__":
    mcp.run(transport="stdio")
