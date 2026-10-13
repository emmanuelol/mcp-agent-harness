import pytest
import pandas as pd
from mcp_agent_harness.server import AgentHarness
from mcp_agent_harness.guards import ToolRateLimitError


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
    assert result["error_code"] == "TokenStarvationError"
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
    assert result["error_code"] == "TokenStarvationError"
    assert "Raw DataFrames are strictly prohibited" in result["message"]
    assert "trace_id" in result


def test_call_tool_unregistered_raises():
    harness = AgentHarness("test-missing", "Missing test", register_builtins=False)
    with pytest.raises(ValueError, match="not registered"):
        harness.call_tool("nonexistent_tool")


def test_declarative_max_chars_and_xml_stripping():
    harness = AgentHarness("test-bounds", register_builtins=False)

    @harness.tool(max_chars=50, strip_xml=True)
    def heavy_tool() -> str:
        return "Start <SECRET>bulk_data</SECRET> End and some extra long repetitive filler characters"

    result = harness.call_tool("heavy_tool")
    assert isinstance(result, str)
    assert "bulk_data" not in result
    assert "[SECRET data omitted — see scalar metrics]" in result
    assert "... [truncated" in result


def test_declarative_max_lines():
    harness = AgentHarness("test-lines", register_builtins=False)

    @harness.tool(max_lines=5)
    def verbose_logs() -> str:
        return "\n".join([f"log line {i}" for i in range(20)])

    result = harness.call_tool("verbose_logs")
    assert isinstance(result, str)
    assert result.count("\n") <= 6
    assert "capped at 5" in result


def test_declarative_catch_unhandled_true():
    harness = AgentHarness("test-envelope", register_builtins=False)

    @harness.tool(catch_unhandled=True)
    def failing_tool() -> str:
        raise RuntimeError("Database connection refused")

    result = harness.call_tool("failing_tool")
    assert result["status"] == "error"
    assert result["error_code"] == "RuntimeError"
    assert "Database connection refused" in result["message"]
    assert "trace_id" in result


def test_declarative_catch_unhandled_false_raises():
    harness = AgentHarness("test-raises", register_builtins=False)

    @harness.tool(catch_unhandled=False)
    def crashing_tool() -> str:
        raise ValueError("Invalid argument supplied")

    with pytest.raises(ValueError, match="Invalid argument supplied"):
        harness.call_tool("crashing_tool")


def test_declarative_rate_limit_raises_when_uncaught():
    harness = AgentHarness("test-ratelimit-raise", register_builtins=False)

    @harness.tool(rate_limit=(3, 60.0), catch_unhandled=False)
    def throttled_tool() -> str:
        return "ok"

    assert harness.call_tool("throttled_tool") == "ok"
    assert harness.call_tool("throttled_tool") == "ok"
    assert harness.call_tool("throttled_tool") == "ok"

    with pytest.raises(ToolRateLimitError, match="Rate limit exceeded"):
        harness.call_tool("throttled_tool")


def test_declarative_rate_limit_returns_envelope_when_caught():
    harness = AgentHarness("test-ratelimit-caught", register_builtins=False)

    @harness.tool(rate_limit=(3, 60.0), catch_unhandled=True)
    def throttled_tool() -> str:
        return "ok"

    assert harness.call_tool("throttled_tool") == "ok"
    assert harness.call_tool("throttled_tool") == "ok"
    assert harness.call_tool("throttled_tool") == "ok"

    result = harness.call_tool("throttled_tool")
    assert result["status"] == "error"
    assert result["error_code"] == "ToolRateLimitError"
    assert "Rate limit exceeded" in result["message"]
    assert "trace_id" in result


@pytest.mark.asyncio
async def test_async_declarative_guards_and_rate_limit():
    harness = AgentHarness("test-async-guards", register_builtins=False)

    @harness.tool(max_chars=40, rate_limit=(2, 60.0), catch_unhandled=True)
    async def async_guarded_tool(msg: str) -> str:
        if msg == "error":
            raise RuntimeError("Async boom")
        return f"Echo: {msg * 10}"

    res1 = await harness.call_tool("async_guarded_tool", msg="hello")
    assert isinstance(res1, str)
    assert "... [truncated" in res1

    res2 = await harness.call_tool("async_guarded_tool", msg="error")
    assert res2["status"] == "error"
    assert res2["error_code"] == "RuntimeError"

    # 3rd invocation hits rate limit
    res3 = await harness.call_tool("async_guarded_tool", msg="hello")
    assert res3["status"] == "error"
    assert res3["error_code"] == "ToolRateLimitError"


def test_decorator_without_parentheses():
    harness = AgentHarness("test-no-parens", register_builtins=False)

    @harness.tool
    def simple_ping() -> str:
        return "pong"

    assert harness.call_tool("simple_ping") == "pong"
