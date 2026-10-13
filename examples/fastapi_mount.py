"""
examples/fastapi_mount.py — Side-by-Side: Unguarded FastMCP vs. AgentHarness SRE Firewall
"""
import pandas as pd
import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp_agent_harness import AgentHarness

# ============================================================================
# 1. UNGUARDED FastMCP Instance (Vulnerable to Token Starvation & OOM)
# ============================================================================
raw_mcp = FastMCP("unguarded-mcp")


@raw_mcp.tool()
def unguarded_financial_query() -> dict:
    """
    ❌ VULNERABLE: Leaks a 100,000-row DataFrame and unclosed raw XML blocks.
    Causes prompt token exhaustion, agent hallucination loops, and crashes SSE.
    """
    raw_df = pd.DataFrame({"transaction_id": range(1000), "amount": [99.5] * 1000})
    raw_xml_logs = "<DATA>" + ("log_event_payload\n" * 500) + "</DATA>"
    # Returning raw DataFrame or unescaped XML directly to LLM context
    return {
        "status": "raw",
        "data": raw_df,  # Will blow up context window
        "logs": raw_xml_logs,
    }


# ============================================================================
# 2. SRE-HARDENED AgentHarness Instance (Token Defense & Fault Isolation)
# ============================================================================
harness = AgentHarness(
    name="hardened-mcp",
    instructions="Production SRE-hardened tools for autonomous operations.",
    register_builtins=True,
)


@harness.tool(
    max_chars=300,
    max_lines=10,
    rate_limit=(5, 60.0),
    catch_unhandled=True,
)
def guarded_financial_query() -> str:
    """
    🛡️ PROTECTED:
    1. Declarative context bounding (truncates XML, caps at 300 chars, max 10 lines).
    2. Per-tool sliding window rate limit (5 calls / 60s).
    3. Fail-closed error envelopes (SSE stream never terminates on panic).
    4. DataFrame blockade prevents tabular data leakage.
    """
    raw_xml_logs = "Header\n<DATA>heavy,unaggregated,csv,data,here</DATA>\nFooter line"
    return raw_xml_logs


@harness.tool(catch_unhandled=True)
def guarded_leaky_data_attempt() -> dict:
    """
    🛡️ BLOCKED: Attempting to return a raw DataFrame immediately triggers
    TokenStarvationError, returning a structured JSON error envelope.
    """
    df = pd.DataFrame({"account_id": [1, 2], "balance": [500.0, 1200.0]})
    return {"status": "ok", "dataframe": df}


# ============================================================================
# 3. Mount into Primary FastAPI Application
# ============================================================================
app = FastAPI(title="MCP Agent Gateway Showcase")

# Mount hardened SRE harness at /mcp
app.mount("/mcp", harness.sse_app())


@app.get("/health")
def health() -> dict:
    return {"status": "operational", "firewall": "active"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
