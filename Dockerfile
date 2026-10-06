# Multi-stage Dockerfile for mcp-agent-harness

# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install library and test dependencies into isolated prefix
RUN pip install --no-cache-dir --prefix=/install ".[dev]"

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Apply OS security patches
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies and binaries from builder
COPY --from=builder /install /usr/local

# Security hardening: remove build tools and bundled wheels from runtime
RUN python -m pip uninstall -y pip setuptools wheel 2>/dev/null || true && \
    rm -rf /usr/local/lib/python3.11/ensurepip
COPY examples/ ./examples/
COPY tests/ ./tests/
COPY pyproject.toml ./

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "-m", "mcp_agent_harness"]
CMD ["--check"]
