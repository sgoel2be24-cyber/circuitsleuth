# MCP integration

CircuitSleuth exposes its inspection tools through a real MCP server (official
Python SDK, stdio transport): `backend/app/tools/mcp_server.py`.

The tools are the **same implementations** the orchestrator uses internally —
an MCP client drives a real persisted inspection, not a simulation.

## Tools

| Tool | Purpose |
|---|---|
| `get_inspection_context` | current state, candidates, available views, budget |
| `align_images` | register test → reference; `recovery=true` retries with CLAHE |
| `detect_defects` | run anomaly detection, return candidate regions + scores |
| `inspect_region` | run a secondary analysis: `highres_zoom`, `edge_topology`, `adaptive_threshold`, `local_realignment`, `alternate_view`, `request_capture` |
| `request_additional_view` | consult the secondary view or return explicit `additional_capture_required` |
| `verify_candidate` | combine evidence into the final verdict |
| `request_human_review` | create an operator review task |
| `generate_inspection_report` | produce the structured final report |

All tools: validated inputs, JSON outputs, explicit failure statuses,
persisted audit events, bounded execution.

## Configuration

Copy `mcp_config.example.json` and point the command at your interpreter:

```json
{
  "mcpServers": {
    "circuitsleuth": {
      "command": ".venv/Scripts/python.exe",
      "args": ["backend/app/tools/mcp_server.py"]
    }
  }
}
```

Works with Claude Desktop (`claude_desktop_config.json`), MCP Inspector
(`npx @modelcontextprotocol/inspector .venv/Scripts/python.exe backend/app/tools/mcp_server.py`)
or any MCP client.

## Try it without a client

```bash
.venv/Scripts/python.exe backend/app/tools/mcp_server.py
# speaks MCP over stdio; create an inspection first via the REST API
```

Note: run MCP sessions against inspections that are not currently executing in
the API process (the server refuses `running` inspections to protect state).
