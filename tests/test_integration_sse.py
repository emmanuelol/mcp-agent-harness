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
