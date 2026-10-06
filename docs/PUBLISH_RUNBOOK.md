# Containerized Publish Runbook: mcp-agent-harness

SRE-compliant procedure for publishing releases and updating consumer services.

## Prerequisites

- Docker and Docker Compose installed.
- No host Python, pip, or virtualenv required.

## Phase 1: Local Verification

1. **Build Container Image**:
   ```bash
   make build
   ```
2. **Execute In-Container Test Suite**:
   ```bash
   make test
   ```
3. **Execute Security & Image Audit**:
   ```bash
   ./scripts/audit_image.sh
   ```

## Phase 2: Remote Publication

1. Initialize Git repository and create release tag:
   ```bash
   git init
   git add .
   git commit -m "feat: SRE-hardened mcp-agent-harness containerized baseline"
   git tag v0.1.0
   ```
2. Push to target GitHub repository:
   ```bash
   git remote add origin https://github.com/<org>/mcp-agent-harness.git
   git push -u origin main --tags
   ```
3. Verify GitHub Actions workflow status is green.

## Phase 3: Consumer Integration (Paseo MS)

1. Obtain exact commit SHA:
   ```bash
   git rev-parse HEAD
   ```
2. In consumer `Dockerfile.scheduler`, pin dependency:
   ```dockerfile
   RUN pip install --no-cache-dir \
       "git+https://github.com/<org>/mcp-agent-harness.git@<commit-sha>#egg=mcp-agent-harness"
   ```
3. Rebuild consumer container:
   ```bash
   docker compose build scheduler
   ```
4. Verify non-root import inside container:
   ```bash
   docker compose run --rm --entrypoint "python -c 'from mcp_agent_harness.guards import block_raw_dataframes; print(\"OK\")'" scheduler
   ```
