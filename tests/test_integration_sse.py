import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp_agent_harness.server import AgentHarness


def test_fastapi_mount_and_sse_initialization():
    app = FastAPI(title="Integration App")
    harness = AgentHarness(name="integration-harness", register_builtins=True)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    # Mount FastMCP SSE ASGI sub-app
    sse_subapp = harness.sse_app()
    app.mount("/mcp", sse_subapp)

    # 1. Verify ASGI sub-application registered expected endpoints
    route_paths = [route.path for route in sse_subapp.routes]
    assert "/sse" in route_paths
    assert "/messages" in route_paths

    with TestClient(app, base_url="http://localhost:8000") as client:
        # 2. Host health endpoint responds
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "ok"}

        # 3. Verify /mcp/sse endpoint is mounted (FastMCP responds with 405 to non-GET)
        options_resp = client.options("/mcp/sse")
        assert options_resp.status_code in [200, 405]

        # 4. JSON-RPC POST endpoint is routed (FastMCP validates session and returns 400)
        msg_resp = client.post("/mcp/messages")
        assert msg_resp.status_code in [200, 400, 405, 422]


def test_declarative_guarded_tool_mounted_in_fastapi():
    app = FastAPI(title="Declarative Guarded App")
    harness = AgentHarness(name="declarative-harness", register_builtins=True)

    @harness.tool(max_chars=50, rate_limit=(2, 60.0), catch_unhandled=True)
    def query_service_status(region: str) -> str:
        if region == "fail":
            raise ConnectionResetError("Remote server disconnected")
        return f"Operational region status: {region} with detailed metrics block <DATA>sensitive</DATA>"

    app.mount("/mcp", harness.sse_app())

    with TestClient(app, base_url="http://localhost:8000") as client:
        # Test tool registry includes declarative tool
        tools = harness.list_tools()
        assert "query_service_status" in tools

        # Direct execution through harness within mounted app lifecycle
        res1 = harness.call_tool("query_service_status", region="us-east-1")
        assert isinstance(res1, str)
        assert "sensitive" not in res1
        assert "... [truncated" in res1

        # Second call succeeds
        res2 = harness.call_tool("query_service_status", region="fail")
        assert res2["status"] == "error"
        assert res2["error_code"] == "ConnectionResetError"
        assert "trace_id" in res2

        # 3rd call triggers rate limit envelope
        res3 = harness.call_tool("query_service_status", region="us-west-2")
        assert res3["status"] == "error"
        assert res3["error_code"] == "ToolRateLimitError"
        assert "trace_id" in res3
