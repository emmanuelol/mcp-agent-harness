# MCP Agent Harness

[![CI Pipeline](https://github.com/emmanuelol/mcp-agent-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/emmanuelol/mcp-agent-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Generic, SRE-hardened Model Context Protocol (MCP) harness for autonomous agents.

## Quickstart (Containerized)

No local Python required. All commands run via Docker.

```bash
make build
make test
make demo
```

## SRE Hardening Principles

1. **Token Starvation Guards**: Prevents raw DataFrames (`pandas`, `polars`) from leaking into LLM context windows. Enforces scalar metric summaries.
2. **Context Bounds**: Automatically truncates bulk `<DATA>` payloads and caps log output lines.
3. **Telemetry Tracing**: Generates correlated `trace_id` for every tool invocation.
4. **Fail-Closed Isolation**: Unhandled exceptions return structured error envelopes without terminating SSE streams.

## Integration with Backends

Install via pip in your consumer Dockerfile:

```dockerfile
RUN pip install "git+https://github.com/emmanuelol/mcp-agent-harness.git@v0.1.0"
```

Mount into FastAPI:

```python
from fastapi import FastAPI
from mcp_agent_harness.server import AgentHarness

harness = AgentHarness(
    name="my-service-mcp",
    instructions="Operational agent tools.",
)

@harness.tool()
def get_status() -> dict:
    return {"status": "ok"}

app = FastAPI()
app.mount("/mcp", harness.sse_app())
```
