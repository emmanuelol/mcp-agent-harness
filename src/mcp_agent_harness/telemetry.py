import uuid
import logging
from typing import Any

logger = logging.getLogger(__name__)


def init_trace(tool_name: str, **kwargs: Any) -> str:
    """
    Initializes telemetry context and assigns a correlated trace ID.
    Eliminates NO_TRACE_ID alerts when deep-stack operations fail.
    """
    trace_id = f"mcp-{uuid.uuid4().hex[:8]}"
    sanitized_kwargs = {k: str(v)[:100] for k, v in kwargs.items() if v is not None}

    logger.debug(
        f"[mcp:{tool_name}] Initialized telemetry trace_id={trace_id} | args={sanitized_kwargs}"
    )
    return trace_id
