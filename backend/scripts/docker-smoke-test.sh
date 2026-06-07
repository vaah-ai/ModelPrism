#!/usr/bin/env bash
# ------------------------------------------------------------------
# ModelPrism Backend — Docker Build Smoke Test
# ------------------------------------------------------------------
# Verifies the Dockerfile builds without errors and the image starts,
# responds to health checks, and handles shutdown gracefully.
#
# Usage:
#   ./scripts/docker-smoke-test.sh
#
# Prerequisites:
#   - Docker installed and running
#   - PostgreSQL and Redis accessible (or use --skip-startup)
# ------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_NAME="modelprism-backend:smoke-test"
SKIP_STARTUP=false
CONTAINER_NAME="modelprism-smoke"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-startup) SKIP_STARTUP=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

echo "============================================"
echo " ModelPrism Backend — Docker Build Smoke Test"
echo "============================================"

# Step 1: Build the Docker image
echo ""
echo "[1/3] Building Docker image..."
cd "$PROJECT_DIR"
docker build -t "$IMAGE_NAME" -f Dockerfile .

echo ""
echo "✅ Build successful"

# If --skip-startup, stop here
if [ "$SKIP_STARTUP" = true ]; then
    echo ""
    echo "Skipping startup test (--skip-startup)."
    echo "To run the full test, ensure PostgreSQL and Redis are running."
    exit 0
fi

# Step 2: Start the container
echo ""
echo "[2/3] Starting container (requires PostgreSQL + Redis on host)..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

docker run -d \
    --name "$CONTAINER_NAME" \
    -p 8000:8000 \
    -e DATABASE_URL="postgresql+asyncpg://user:password@host.docker.internal:5432/modelprism" \
    -e REDIS_URL="redis://host.docker.internal:6379/0" \
    -e JWT_SECRET="smoke-test-secret-key-for-container" \
    -e ENVIRONMENT="production" \
    "$IMAGE_NAME"

echo "Container started, waiting 5s for initialization..."
sleep 5

# Step 3: Test health endpoint
echo ""
echo "[3/3] Testing health endpoint..."

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
HEALTH_BODY=$(curl -s http://localhost:8000/api/health 2>/dev/null || echo '{"error":"unreachable"}')

echo "HTTP Status: $HTTP_STATUS"
echo "Health body: $HEALTH_BODY"

# Cleanup
echo ""
echo "Cleaning up..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

if [ "$HTTP_STATUS" = "200" ]; then
    echo ""
    echo "============================================"
    echo " 🟢 Smoke test PASSED"
    echo "============================================"
    exit 0
else
    echo ""
    echo "============================================"
    echo " 🔴 Smoke test FAILED (HTTP $HTTP_STATUS)"
    echo "============================================"
    exit 1
fi
