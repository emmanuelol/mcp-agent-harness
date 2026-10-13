import argparse
import inspect
import json
import logging
import sys
from functools import wraps
from typing import Any, Callable, Optional

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP

from .guards import (
    TokenStarvationError,
    ToolRateLimitError,
    SlidingWindowLimiter,
    block_raw_dataframes,
    cap_log_lines,
    truncate_context,
)
from .telemetry import init_trace

logger = logging.getLogger(__name__)


class ToolInfo(str):
    """String representing a tool name with backwards-compatible .name attribute."""

    @property
    def name(self) -> str:
        return str(self)


class ToolList(list):
    """List of tools supporting both synchronous iteration and async awaiting."""

    def __await__(self):
        async def _resolve():
            return self
        return _resolve().__await__()


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
        self._tools: dict[str, Callable] = {}
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

    def tool(
        self,
        *args: Any,
        max_chars: Optional[int] = None,
        max_lines: Optional[int] = None,
        strip_xml: bool = True,
        catch_unhandled: bool = False,
        rate_limit: Optional[tuple[int, float]] = None,
        **kwargs: Any,
    ) -> Callable:
        """
        Decorator wrapping FastMCP tool registration.
        Supports both synchronous and asynchronous tools.
        Enforces telemetry tracing, rate limiting, and declarative boundary guards.
        """
        limiter = (
            SlidingWindowLimiter(max_calls=rate_limit[0], period_seconds=rate_limit[1])
            if rate_limit is not None
            else None
        )

        def decorator(func: Callable) -> Callable:
            tool_name = kwargs.get("name") or getattr(func, "__name__", str(func))
            if inspect.iscoroutinefunction(func):

                @wraps(func)
                async def async_wrapper(*f_args: Any, **f_kwargs: Any) -> Any:
                    trace_id = init_trace(func.__name__, **f_kwargs)
                    try:
                        if limiter is not None:
                            limiter.acquire()
                        result = await func(*f_args, **f_kwargs)
                        block_raw_dataframes(result)
                        if max_lines is not None and isinstance(result, str):
                            result = cap_log_lines(result, max_lines=max_lines)
                        if max_chars is not None and isinstance(result, str):
                            result = truncate_context(result, max_chars=max_chars, strip_xml=strip_xml)
                        return result
                    except TokenStarvationError as e:
                        logger.error(
                            f"[mcp:{func.__name__}] Async tool token starvation guard | trace_id={trace_id} | error={str(e)}"
                        )
                        return {
                            "status": "error",
                            "error_code": "TokenStarvationError",
                            "message": str(e),
                            "trace_id": trace_id,
                        }
                    except Exception as e:
                        if not catch_unhandled:
                            raise
                        logger.error(
                            f"[mcp:{func.__name__}] Async tool execution failed | trace_id={trace_id} | error={str(e)}"
                        )
                        return {
                            "status": "error",
                            "error_code": type(e).__name__,
                            "message": str(e),
                            "trace_id": trace_id,
                        }

                self._tools[tool_name] = async_wrapper
                return self.mcp.tool(*args, **kwargs)(async_wrapper)
            else:

                @wraps(func)
                def sync_wrapper(*f_args: Any, **f_kwargs: Any) -> Any:
                    trace_id = init_trace(func.__name__, **f_kwargs)
                    try:
                        if limiter is not None:
                            limiter.acquire()
                        result = func(*f_args, **f_kwargs)
                        block_raw_dataframes(result)
                        if max_lines is not None and isinstance(result, str):
                            result = cap_log_lines(result, max_lines=max_lines)
                        if max_chars is not None and isinstance(result, str):
                            result = truncate_context(result, max_chars=max_chars, strip_xml=strip_xml)
                        return result
                    except TokenStarvationError as e:
                        logger.error(
                            f"[mcp:{func.__name__}] Sync tool token starvation guard | trace_id={trace_id} | error={str(e)}"
                        )
                        return {
                            "status": "error",
                            "error_code": "TokenStarvationError",
                            "message": str(e),
                            "trace_id": trace_id,
                        }
                    except Exception as e:
                        if not catch_unhandled:
                            raise
                        logger.error(
                            f"[mcp:{func.__name__}] Sync tool execution failed | trace_id={trace_id} | error={str(e)}"
                        )
                        return {
                            "status": "error",
                            "error_code": type(e).__name__,
                            "message": str(e),
                            "trace_id": trace_id,
                        }

                self._tools[tool_name] = sync_wrapper
                return self.mcp.tool(*args, **kwargs)(sync_wrapper)

        if len(args) == 1 and callable(args[0]):
            target_func = args[0]
            args = ()
            return decorator(target_func)

        return decorator

    def list_tools(self) -> ToolList:
        """Returns list of registered tool names, compatible with sync and async callers."""
        return ToolList([ToolInfo(name) for name in self._tools.keys()])

    def call_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Directly invoke registered tool by name (ideal for tests and isolated calls)."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' is not registered in harness.")
        return self._tools[name](*args, **kwargs)

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
        tools = harness.list_tools()
        output = {
            "status": "healthy",
            "tools_registered": len(tools),
            "tools": tools,
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        import uvicorn
        from fastapi import FastAPI

        harness = AgentHarness(name="mcp-agent-harness", register_builtins=True)
        app = FastAPI(title="MCP Agent Harness")

        @app.get("/health")
        def health_check() -> dict:
            return {"status": "ok"}

        app.mount("/mcp", harness.sse_app())
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
