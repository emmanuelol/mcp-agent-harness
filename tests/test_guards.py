import pytest
import pandas as pd
from mcp_agent_harness.guards import (
    block_raw_dataframes,
    truncate_context,
    cap_log_lines,
    _is_dataframe,
    TokenStarvationError,
    ToolRateLimitError,
    SlidingWindowLimiter,
)


def test_dataframe_blockade():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(TokenStarvationError):
        block_raw_dataframes(df)


def test_series_blockade():
    s = pd.Series([1, 2, 3])
    with pytest.raises(TokenStarvationError):
        block_raw_dataframes(s)


def test_nested_dataframe_blockade():
    df = pd.DataFrame({"col": [10, 20]})
    nested_payload = {
        "status": "success",
        "nested": [{"data": df}],
    }
    with pytest.raises(TokenStarvationError):
        block_raw_dataframes(nested_payload)


def test_is_dataframe_polars_and_pyarrow_mro_duck_typing():
    # Simulate polars DataFrame
    class PolarsFakeDataFrame:
        pass
    PolarsFakeDataFrame.__module__ = "polars.dataframe.frame"
    PolarsFakeDataFrame.__name__ = "DataFrame"
    fake_pl = PolarsFakeDataFrame()
    assert _is_dataframe(fake_pl) is True

    # Simulate pyarrow Table
    class PyArrowFakeTable:
        pass
    PyArrowFakeTable.__module__ = "pyarrow.lib"
    PyArrowFakeTable.__name__ = "Table"
    fake_pa = PyArrowFakeTable()
    assert _is_dataframe(fake_pa) is True

    # Regular dict/list/string should not trigger
    assert _is_dataframe({"a": 1}) is False
    assert _is_dataframe([1, 2, 3]) is False
    assert _is_dataframe("test string") is False
    assert _is_dataframe(None) is False


def test_circular_reference_handled_safely():
    cyclic_dict = {"status": "ok"}
    cyclic_dict["self"] = cyclic_dict
    # Should not raise RecursionError
    block_raw_dataframes(cyclic_dict)


def test_deep_nesting_fails_closed():
    nested = {}
    curr = nested
    for _ in range(60):
        curr["child"] = {}
        curr = curr["child"]
    with pytest.raises(TokenStarvationError, match="exceeds 50 levels"):
        block_raw_dataframes(nested)


def test_truncate_context_strips_data_blocks():
    raw_context = "Prefix <DATA>1,2,3,heavy,csv</DATA> Suffix"
    result = truncate_context(raw_context)
    assert "[DATA data omitted — see scalar metrics]" in result
    assert "heavy,csv" not in result


def test_truncate_context_max_chars():
    long_text = "x" * 5000
    result = truncate_context(long_text, max_chars=2000)
    assert len(result) <= 2100
    assert "[truncated" in result


def test_cap_log_lines():
    lines = "\n".join([f"line {i}" for i in range(500)])
    result = cap_log_lines(lines, max_lines=200)
    assert result.count("\n") <= 202
    assert "capped at 200" in result


def test_sliding_window_limiter():
    limiter = SlidingWindowLimiter(max_calls=3, period_seconds=60.0)
    # First 3 calls succeed
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    # 4th call raises ToolRateLimitError
    with pytest.raises(ToolRateLimitError, match="Rate limit exceeded: 3 calls per 60.0s"):
        limiter.acquire()


def test_sliding_window_limiter_validation():
    with pytest.raises(ValueError, match="max_calls must be positive"):
        SlidingWindowLimiter(max_calls=0, period_seconds=10.0)
    with pytest.raises(ValueError, match="period_seconds must be positive"):
        SlidingWindowLimiter(max_calls=5, period_seconds=0.0)
