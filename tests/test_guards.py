import pytest
from mcp_agent_harness.guards import (
    block_raw_dataframes,
    truncate_context,
    cap_log_lines,
    TokenStarvationError,
)


class DataFrame:
    __module__ = "pandas.core.frame"


def test_dataframe_blockade():
    try:
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2, 3]})
    except ImportError:
        df = DataFrame()

    with pytest.raises(TokenStarvationError):
        block_raw_dataframes(df)


def test_nested_dataframe_blockade():
    try:
        import pandas as pd
        df = pd.DataFrame({"col": [10, 20]})
    except ImportError:
        df = DataFrame()

    nested_payload = {
        "status": "success",
        "nested": [
            {"data": df}
        ]
    }
    with pytest.raises(TokenStarvationError):
        block_raw_dataframes(nested_payload)


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
