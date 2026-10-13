"""
mcp_agent_harness
=================
Generic, SRE-hardened Model Context Protocol (MCP) harness for autonomous agents.
"""

from .guards import (
    TokenStarvationError,
    ToolRateLimitError,
    SlidingWindowLimiter,
    block_raw_dataframes,
    truncate_context,
    cap_log_lines,
)
from .server import AgentHarness
from .telemetry import init_trace

__all__ = [
    "AgentHarness",
    "TokenStarvationError",
    "ToolRateLimitError",
    "SlidingWindowLimiter",
    "block_raw_dataframes",
    "truncate_context",
    "cap_log_lines",
    "init_trace",
]

__version__ = "0.2.0"
