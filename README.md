# MCP Agent Harness

[![CI Pipeline](https://github.com/emmanuelol/mcp-agent-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/emmanuelol/mcp-agent-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Generic, SRE-hardened Model Context Protocol (MCP) harness for autonomous agents. Designed to prevent LLM context exhaustion, enforce data boundaries, and maintain fail-closed observability across agentic workloads.

---

## Prerequisites

- **Docker** `>= 24.0`
- **Docker Compose** `>= 2.20`
- **GNU Make** `>= 4.3`
- *(Optional for local development)* **Python** `>= 3.11`

---

## Quickstart (Containerized)

No local Python environment or dependency installation required. All lifecycle steps run inside isolated containers:

```bash
# 1. Build the hardened container image
make build

# 2. Run the integration test suite
make test

# 3. Spin up the harness and verify live endpoint health
make demo

# 4. Run the security, leak, and Trivy CVE audit gate
make audit
```

---

## Architecture & Codebase Map

```text
mcp-agent-harness/
├── src/
│   └── mcp_agent_harness/
│       ├── __init__.py      # Public exports: AgentHarness, guards, telemetry
│       ├── server.py        # AgentHarness, ToolList, tool decorator, SSE app mounting
│       ├── guards.py        # DataFrame blockade, TokenStarvationError, context & log capping
│       ├── telemetry.py     # Correlated trace_id generation and context logging
│       └── __main__.py      # CLI entrypoint for health checks and standalone daemon
├── tests/
│   ├── test_guards.py       # Unit tests for DataFrame blockade, context truncation, log capping
│   ├── test_server.py       # Sync/async tool execution, leak detection, registry checks
│   └── test_integration_sse.py # FastAPI SSE endpoint mounting and streaming tests
├── scripts/
│   ├── audit_image.sh       # Fail-closed Trivy CVE scanner & prohibited file leak audit
│   └── check_blacklist.sh   # Clean-room sensitive pattern scanner
├── Dockerfile               # Multi-stage hardened Debian container definition
├── docker-compose.yml       # Service definitions for daemon and test runner
└── Makefile                 # Standardized automation targets
```

---

## SRE Hardening Principles

1. **Token Starvation Guards**: Prevents raw DataFrames (`pandas`, `polars`) from leaking into LLM context windows. Enforces scalar metric summaries.
2. **Context Bounds**: Automatically truncates bulk `<DATA>` payloads and caps log output lines to prevent context window blowouts.
3. **Telemetry Tracing**: Generates correlated `trace_id` for every tool invocation.
4. **Fail-Closed Isolation**: Unhandled exceptions return structured error envelopes without terminating SSE streams.

---

## API & Configuration Reference

### `AgentHarness`

Main server class wrapping FastMCP with SRE guards.

```python
from mcp_agent_harness import AgentHarness

harness = AgentHarness(
    name="analytics-mcp",
    instructions="Operational analytics tools for agents.",
    register_builtins=True,
)
```

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `str` | `"mcp-agent-harness"` | Identifier for the MCP server instance. |
| `instructions` | `str` | `"Generic SRE-hardened MCP Harness"` | System instructions exposed to MCP clients. |
| `register_builtins` | `bool` | `True` | Registers default diagnostic tools (`health`, `ping`, `diagnostics`). |

#### Methods

- `@harness.tool(*args, **kwargs)`: Decorator registering sync or `async` tools with automatic trace injection and DataFrame blockades.
- `harness.list_tools() -> ToolList`: Returns registered tool names (supports both sync iteration and async `await`).
- `harness.call_tool(name: str, *args, **kwargs) -> Any`: Directly invokes a registered tool by name.
- `harness.sse_app() -> Any`: Generates the Starlette/ASGI app for mounting into FastAPI.

---

### Guard Utilities (`mcp_agent_harness.guards`)

Configurable standalone filters to protect agent prompt budgets:

| Function | Parameters | Default | Description |
| :--- | :--- | :--- | :--- |
| `truncate_context()` | `context: Any, max_chars: int = 2000, strip_xml: bool = True` | `max_chars=2000` | Strips raw `<DATA>...</DATA>` XML blocks and truncates strings exceeding character limits. |
| `cap_log_lines()` | `text: Any, max_lines: int = 200` | `max_lines=200` | Caps multiline log dumps to prevent terminal context flooding. |
| `block_raw_dataframes()` | `obj: Any` | N/A | Recursively traverses dicts, lists, sets, and tuples, raising `TokenStarvationError` if a DataFrame is detected. |

---

## Guardrails in Action

### 1. Synchronous & Asynchronous Tools

```python
from mcp_agent_harness import AgentHarness

harness = AgentHarness(name="system-tools")

# Synchronous tool
@harness.tool()
def get_system_load() -> dict:
    return {"load_1m": 0.42, "load_5m": 0.35}

# Asynchronous tool
@harness.tool()
async def fetch_cluster_metrics(region: str) -> dict:
    # Non-blocking async execution
    return {"region": region, "active_nodes": 12, "healthy": True}
```

### 2. Token Starvation Guard (DataFrame Blockade)

The harness blocks raw tabular data from entering LLM context. Returning a raw DataFrame immediately triggers `TokenStarvationError`, captured into a structured error envelope:

```python
import pandas as pd
from mcp_agent_harness import AgentHarness

harness = AgentHarness()

# ❌ BAD: Attempting to return raw DataFrame
@harness.tool()
def query_orders() -> pd.DataFrame:
    return pd.DataFrame({"order_id": [1, 2], "amount": [99.5, 14.2]})

# Invoking this tool returns a safe error envelope instead of leaking rows:
# {
#   "status": "error",
#   "message": "Raw DataFrames are strictly prohibited in MCP tools. Return scalar metrics or token-compressed strings.",
#   "trace_id": "mcp-3a1b4c9e"
# }

# ✅ GOOD: Return compact scalar metrics
@harness.tool()
def query_order_metrics() -> dict:
    df = pd.DataFrame({"order_id": [1, 2], "amount": [99.5, 14.2]})
    return {
        "order_count": len(df),
        "total_revenue": float(df["amount"].sum()),
        "average_order": float(df["amount"].mean()),
    }
```

### 3. Context & Log Bounds

```python
from mcp_agent_harness import truncate_context, cap_log_lines

raw_logs = "INFO: Step completed\n" * 500
# Safe for LLM prompts: capped at 200 lines
clean_logs = cap_log_lines(raw_logs, max_lines=200)

raw_prompt = "User query: analyze output <DATA>large blob...</DATA>"
# Strips bulk data XML tags and caps character length
bounded_prompt = truncate_context(raw_prompt, max_chars=1000)
```

---

## Telemetry & Error Envelopes

Every tool invocation automatically initializes an OpenTelemetry-compatible `trace_id` (`mcp-xxxxxxxx`). 

When an unhandled exception occurs inside a tool, the harness isolates the failure:
- The underlying SSE stream remains open.
- The failure is logged with the correlated trace ID.
- The agent receives a predictable JSON envelope:

```json
{
  "status": "error",
  "message": "Division by zero",
  "trace_id": "mcp-e4f912a7"
}
```

---

## Integration with FastAPI

Install the package in your consumer application:

```bash
pip install "git+https://github.com/emmanuelol/mcp-agent-harness.git@v0.1.0"
```

Mount into FastAPI:

```python
from fastapi import FastAPI
from mcp_agent_harness import AgentHarness

harness = AgentHarness(
    name="production-harness",
    instructions="Production operational agent harness.",
)

@harness.tool()
async def health_summary() -> dict:
    return {"status": "operational", "uptime_pct": 99.98}

app = FastAPI(title="Agent Platform")

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

# Mount MCP Server-Sent Events endpoint
app.mount("/mcp", harness.sse_app())
```

Run with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
