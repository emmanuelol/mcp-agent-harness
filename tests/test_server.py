import pytest
from mcp_agent_harness.server import AgentHarness


class DataFrame:
    __module__ = "pandas.core.frame"


def test_harness_init_and_default_tools():
    harness = AgentHarness("test-harness", "Test instructions", register_builtins=True)
    tools = harness.mcp._tool_manager.list_tools()
    assert len(tools) == 3
    tool_names = [t.name for t in tools]
    assert "health" in tool_names
    assert "ping" in tool_names
    assert "diagnostics" in tool_names


def test_sync_tool_success_and_trace():
    harness = AgentHarness("test-sync", "Sync test", register_builtins=False)

    @harness.tool()
    def compute_sum(a: int, b: int) -> dict:
        return {"sum": a + b}

    tool_def = harness.mcp._tool_manager.get_tool("compute_sum")
    assert tool_def is not None
    result = tool_def.fn(a=2, b=3)
    assert result == {"sum": 5}


def test_sync_tool_catches_dataframe_leak():
    try:
        import pandas as pd
        df = pd.DataFrame({"x": [1]})
    except ImportError:
        df = DataFrame()

    harness = AgentHarness("test-leak", "Leak test", register_builtins=False)

    @harness.tool()
    def leaky_tool() -> dict:
        return {"df": df}

    tool_def = harness.mcp._tool_manager.get_tool("leaky_tool")
    result = tool_def.fn()
    assert result["status"] == "error"
    assert "Raw DataFrames are strictly prohibited" in result["message"]
    assert "trace_id" in result


@pytest.mark.asyncio
async def test_async_tool_support_and_leak_detection():
    try:
        import pandas as pd
        df = pd.DataFrame({"y": [2]})
    except ImportError:
        df = DataFrame()

    harness = AgentHarness("test-async", "Async test", register_builtins=False)

    @harness.tool()
    async def async_leaky_tool() -> dict:
        return {"df": df}

    tool_def = harness.mcp._tool_manager.get_tool("async_leaky_tool")
    result = await tool_def.fn()
    assert result["status"] == "error"
    assert "Raw DataFrames are strictly prohibited" in result["message"]
    assert "trace_id" in result
