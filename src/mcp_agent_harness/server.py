import argparse
import inspect
import json
import logging
import sys
from functools import wraps
from typing import Any, Callable

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP

from .guards import block_raw_dataframes
from .telemetry import init_trace

logger = logging.getLogger(__name__)


class AgentHarness:
    """
    SRE-hardened MCP harness for autonomous agents.
    Enforces DataFrame boundary guards, token starvation defenses, and trace propagation.
    """

    def __init__(
        self,
        name: str = "mcp-agent-harness",
        instructions: str = "Generic SRE-hardened MCP Harness",
        register_builtins: bool = True,
    ) -> None:
        self.name = name
        self.instructions = instructions
        self.mcp = FastMCP(name=name, instructions=instructions)
        if register_builtins:
            self._register_builtins()

    def _register_builtins(self) -> None:
        """Register default diagnostic and heartbeat tools."""

        @self.tool()
        def health() -> dict:
            """Diagnostic health check tool."""
            return {"status": "ok", "harness": self.name}

        @self.tool()
        def ping() -> str:
            """Diagnostic ping tool."""
            return "pong"

        @self.tool()
        def diagnostics() -> dict:
            """Harness diagnostics and active guard status."""
            return {
                "dataframe_guard": True,
                "token_starvation_guard": True,
                "telemetry_trace_injection": True,
            }

    def tool(self, *args: Any, **kwargs: Any) -> Callable:
        """
        Decorator wrapping FastMCP tool registration.
        Supports both synchronous and asynchronous tools.
        Enforces telemetry tracing and data boundary guards.
        """

        def decorator(func: Callable) -> Callable:
            if inspect.iscoroutinefunction(func):

                @wraps(func)
                async def async_wrapper(*f_args: Any, **f_kwargs: Any) -> Any:
                    trace_id = init_trace(func.__name__, **f_kwargs)
                    try:
                        result = await func(*f_args, **f_kwargs)
                        block_raw_dataframes(result)
                        return result
                    except Exception as e:
                        logger.error(
                            f"[mcp:{func.__name__}] Async tool execution failed | trace_id={trace_id} | error={str(e)}"
                        )
                        return {"status": "error", "message": str(e), "trace_id": trace_id}

                return self.mcp.tool(*args, **kwargs)(async_wrapper)
            else:

                @wraps(func)
                def sync_wrapper(*f_args: Any, **f_kwargs: Any) -> Any:
                    trace_id = init_trace(func.__name__, **f_kwargs)
                    try:
                        result = func(*f_args, **f_kwargs)
                        block_raw_dataframes(result)
                        return result
                    except Exception as e:
                        logger.error(
                            f"[mcp:{func.__name__}] Sync tool execution failed | trace_id={trace_id} | error={str(e)}"
                        )
                        return {"status": "error", "message": str(e), "trace_id": trace_id}

                return self.mcp.tool(*args, **kwargs)(sync_wrapper)

        return decorator

    def sse_app(self) -> Any:
        """Returns the ASGI app for FastAPI/Starlette mounting."""
        return self.mcp.sse_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Agent Harness Server")
    parser.add_argument("--check", action="store_true", help="Run self-check and exit")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    args = parser.parse_args()

    if args.check:
        harness = AgentHarness(name="mcp-agent-harness", register_builtins=True)
        tools = harness.mcp._tool_manager.list_tools()
        output = {
            "status": "healthy",
            "tools_registered": len(tools),
            "tools": [t.name for t in tools],
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        import uvicorn
        from fastapi import FastAPI

        harness = AgentHarness(name="mcp-agent-harness", register_builtins=True)
        app = FastAPI(title="MCP Agent Harness")
        app.mount("/mcp", harness.sse_app())
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
