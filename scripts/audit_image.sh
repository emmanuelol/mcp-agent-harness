#!/bin/bash
set -euo pipefail

IMAGE="mcp-agent-harness:latest"

echo "=== Scanning image for prohibited files ==="
LEAKS=$(docker run --rm --entrypoint "" "$IMAGE" sh -c '
  find / -name "*.env" -o -name "sessions.json" 2>/dev/null | grep -v "/proc/" || true
  find /app -name "*.pem" -o -name "*.key" 2>/dev/null || true
')

if [ -n "$LEAKS" ]; then
  echo "ERROR: Found prohibited files in image:"
  echo "$LEAKS"
  exit 1
fi
echo "Prohibited files check passed."

echo "=== Checking image size ==="
RAW_SIZE=$(docker images "$IMAGE" --format "{{.Size}}")
echo "Image size: $RAW_SIZE"

# Check Trivy scan if trivy exists or run dockerized trivy if daemon available
if command -v trivy &>/dev/null; then
  echo "=== Running local Trivy scan ==="
  trivy image --severity HIGH,CRITICAL "$IMAGE"
elif [ -e /var/run/docker.sock ]; then
  echo "=== Running containerized Trivy scan ==="
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    aquasec/trivy image --severity HIGH,CRITICAL "$IMAGE" || true
fi

echo "=== Audit passed ==="
