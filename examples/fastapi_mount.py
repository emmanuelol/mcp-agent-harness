import uvicorn
from fastapi import FastAPI
from mcp_agent_harness.server import AgentHarness
from mcp_agent_harness.guards import truncate_context

# 1. Initialize the Generic Harness
harness = AgentHarness(
    name="paseoms-mcp",
    instructions="Backend MCP tools for autonomous operations.",
    register_builtins=True,
)

# 2. Define Private Business Tools using the Harness Decorator
@harness.tool()
def get_financial_context(phone_number: str, days: int = 7) -> dict:
    """
    Retrieve pre-aggregated financial context.
    (In Paseo MS, queries Google Sheets / Odoo).
    """
    # Simulated heavy raw context
    raw_context = "<DATA>date,revenue\n2026-10-01,5000\n2026-10-02,6000</DATA>"

    # Apply guard before returning to LLM
    safe_preview = truncate_context(raw_context)

    return {
        "status": "success",
        "metrics": {"total_revenue": 11000, "upt": 2.4},
        "full_context_preview": safe_preview,
    }


# 3. Mount into FastAPI
app = FastAPI(title="Agent Gateway")
app.mount("/mcp", harness.sse_app())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
