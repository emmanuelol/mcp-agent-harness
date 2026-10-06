"""
mcp_agent_harness
=================
Generic, SRE-hardened Model Context Protocol (MCP) harness for autonomous agents.
"""

from .guards import (
    TokenStarvationError,
    block_raw_dataframes,
    truncate_context,
    cap_log_lines,
)
from .server import AgentHarness
from .telemetry import init_trace

__all__ = [
    "AgentHarness",
    "TokenStarvationError",
    "block_raw_dataframes",
    "truncate_context",
    "cap_log_lines",
    "init_trace",
]

__version__ = "0.1.0"
