# Contributing to MCP Agent Harness

We welcome community contributions. To ensure quality, stability, and token efficiency, all pull requests must follow these guidelines.

## Development Environment (Containerized)

No host dependencies required. All operations run through Docker:

```bash
# Build local container image
make build

# Run complete test suite inside container
make test

# Verify local live endpoint
make demo

# Execute security and secret leak scan
make audit
```

## SRE Rules

1. **Zero Raw DataFrames**: Tools must never return `pandas` or `polars` DataFrames across the tool boundary. Aggregate into scalar dictionaries or compressed text.
2. **Context Limits**: Keep payload strings concise; enforce maximum character truncation via `truncate_context`.
3. **Telemetry**: Always preserve trace correlation IDs for downstream observability.
4. **Clean-Room Standard**: Never commit credentials, proprietary tenant IDs, or private endpoint configurations. All tests must pass `scripts/check_blacklist.sh`.
