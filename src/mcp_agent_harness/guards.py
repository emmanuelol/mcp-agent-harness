import re
import sys
import logging
from typing import Any, Optional
from .telemetry import init_trace

logger = logging.getLogger(__name__)


class TokenStarvationError(Exception):
    """Raised when raw data structures attempt to cross the MCP boundary."""
    pass


def _is_dataframe(obj: Any) -> bool:
    """Check if object is a Pandas or Polars DataFrame without hard imports."""
    if "pandas" in sys.modules:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            return True
    if "polars" in sys.modules:
        import polars as pl
        if isinstance(obj, pl.DataFrame):
            return True
    type_name = type(obj).__name__
    module_name = getattr(type(obj), "__module__", "") or ""
    if "DataFrame" in type_name and ("pandas" in module_name or "polars" in module_name):
        return True
    return False


def block_raw_dataframes(obj: Any) -> None:
    """
    SRE Guard: Prevents Pandas and Polars DataFrames from crossing tool boundary.
    Recursively inspects dicts, lists, tuples, and sets.
    """
    if _is_dataframe(obj):
        raise TokenStarvationError(
            "Raw DataFrames are strictly prohibited in MCP tools. "
            "Return scalar metrics or token-compressed strings."
        )

    if isinstance(obj, dict):
        for val in obj.values():
            block_raw_dataframes(val)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            block_raw_dataframes(item)


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

    if strip_xml:
        clean_context = re.sub(
            r"<([A-Z_]+)>.*?</\1>",
            r"[\1 data omitted — see scalar metrics]",
            context,
            flags=re.DOTALL,
        )
    else:
        clean_context = context

    if len(clean_context) > limit:
        return clean_context[:limit] + f"\n... [truncated, {len(clean_context)} chars total]"

    return clean_context


def cap_log_lines(text: Any, max_lines: int = 200) -> str:
    """
    Caps text output to a maximum number of lines to avoid context flooding.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    lines = text.splitlines()
    if len(lines) > max_lines:
        capped = "\n".join(lines[:max_lines])
        return capped + f"\n... [truncated, {len(lines)} lines total, capped at {max_lines}]"

    return text
