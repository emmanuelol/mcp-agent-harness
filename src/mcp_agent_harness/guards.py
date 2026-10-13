import collections
import logging
import re
import sys
import threading
import time
from typing import Any, Optional
from .telemetry import init_trace

logger = logging.getLogger(__name__)


class TokenStarvationError(Exception):
    """Raised when raw data structures attempt to cross the MCP boundary."""
    pass


class ToolRateLimitError(Exception):
    """Raised when tool invocation frequency exceeds allowed threshold."""
    pass


class SlidingWindowLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, max_calls: int, period_seconds: float) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if period_seconds <= 0:
            raise ValueError("period_seconds must be positive")
        self.max_calls = max_calls
        self.period_seconds = float(period_seconds)
        self._timestamps: collections.deque[float] = collections.deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Records a call or raises ToolRateLimitError if threshold exceeded."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.period_seconds
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_calls:
                raise ToolRateLimitError(
                    f"Rate limit exceeded: {self.max_calls} calls per {self.period_seconds}s limit reached."
                )

            self._timestamps.append(now)


def _is_dataframe(obj: Any) -> bool:
    """Check if object is a Pandas/Polars DataFrame/Series or PyArrow Table via MRO inspection."""
    try:
        mro = type(obj).__mro__
    except (AttributeError, TypeError):
        return False

    target_names = {"DataFrame", "Series", "Table"}
    target_prefixes = ("pandas", "polars", "pyarrow")

    for cls in mro:
        mod = getattr(cls, "__module__", "") or ""
        name = getattr(cls, "__name__", "") or ""
        if name in target_names and mod.startswith(target_prefixes):
            return True
    return False


def block_raw_dataframes(
    obj: Any,
    _depth: int = 0,
    _visited: Optional[set] = None,
) -> None:
    """
    SRE Guard: Prevents Pandas, Polars, and PyArrow data structures from crossing tool boundary.
    Recursively inspects dicts, lists, tuples, and sets with cycle detection and depth capping.
    """
    if _is_dataframe(obj):
        raise TokenStarvationError(
            "Raw DataFrames are strictly prohibited in MCP tools. "
            "Return scalar metrics or token-compressed strings."
        )

    if not isinstance(obj, (dict, list, tuple, set)):
        return

    if _visited is None:
        _visited = set()

    obj_id = id(obj)
    if obj_id in _visited:
        return
    if _depth >= 50:
        raise TokenStarvationError(
            "Payload nesting exceeds 50 levels; return flat scalar metrics or token-compressed strings."
        )

    _visited.add(obj_id)
    children = obj.values() if isinstance(obj, dict) else obj
    for item in children:
        block_raw_dataframes(item, _depth + 1, _visited)


def truncate_context(
    context: Any,
    max_chars: int = 2000,
    max_length: Optional[int] = None,
    strip_xml: bool = True,
) -> str:
    """
    Strips raw <DATA>...</DATA> blocks and truncates context to prevent LLM exhaustion.
    """
    if context is None:
        return ""
    if not isinstance(context, str):
        context = str(context)

    limit = max_length if max_length is not None else max_chars

    # Pre-truncate to safe buffer to prevent ReDoS on massive unclosed XML tags
    safe_buffer = max(limit * 2, 4000)
    original_len = len(context)
    text = context[:safe_buffer] if len(context) > safe_buffer else context

    if strip_xml:
        clean_context = re.sub(
            r"<([A-Z_]+)>.*?</\1>",
            r"[\1 data omitted — see scalar metrics]",
            text,
            flags=re.DOTALL,
        )
    else:
        clean_context = text

    if len(clean_context) > limit or original_len > limit:
        total_len = max(original_len, len(clean_context))
        return clean_context[:limit] + f"\n... [truncated, {total_len} chars total]"

    return clean_context


def cap_log_lines(text: Any, max_lines: int = 200) -> str:
    """
    Caps text output to a maximum number of lines to avoid context flooding.
    """
    if text is None:
        return ""
    if isinstance(text, list):
        lines = [str(x) for x in text]
    else:
        lines = str(text).splitlines()

    if len(lines) > max_lines:
        capped = "\n".join(lines[:max_lines])
        return capped + f"\n... [truncated, {len(lines)} lines total, capped at {max_lines}]"

    return "\n".join(lines) if isinstance(text, list) else str(text)
