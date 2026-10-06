import pytest
import pandas as pd
from mcp_agent_harness.server import AgentHarness


def test_harness_init_and_default_tools():
    harness = AgentHarness("test-harness", "Test instructions", register_builtins=True)
    tools = harness.list_tools()
    assert len(tools) == 3
    assert "health" in tools
    assert "ping" in tools
    assert "diagnostics" in tools


def test_sync_tool_success_and_trace():
    harness = AgentHarness("test-sync", "Sync test", register_builtins=False)

    @harness.tool()
    def compute_sum(a: int, b: int) -> dict:
        return {"sum": a + b}

    result = harness.call_tool("compute_sum", a=2, b=3)
    assert result == {"sum": 5}


def test_sync_tool_catches_dataframe_leak():
    df = pd.DataFrame({"x": [1]})
    harness = AgentHarness("test-leak", "Leak test", register_builtins=False)

    @harness.tool()
    def leaky_tool() -> dict:
        return {"df": df}

    result = harness.call_tool("leaky_tool")
    assert result["status"] == "error"
    assert "Raw DataFrames are strictly prohibited" in result["message"]
    assert "trace_id" in result


@pytest.mark.asyncio
async def test_async_tool_support_and_leak_detection():
    df = pd.DataFrame({"y": [2]})
    harness = AgentHarness("test-async", "Async test", register_builtins=False)

    @harness.tool()
    async def async_leaky_tool() -> dict:
        return {"df": df}

    result = await harness.call_tool("async_leaky_tool")
    assert result["status"] == "error"
    assert "Raw DataFrames are strictly prohibited" in result["message"]
    assert "trace_id" in result


def test_call_tool_unregistered_raises():
    harness = AgentHarness("test-missing", "Missing test", register_builtins=False)
    with pytest.raises(ValueError, match="not registered"):
        harness.call_tool("nonexistent_tool")
