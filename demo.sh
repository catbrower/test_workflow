#!/usr/bin/env bash
set -euo pipefail

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "==> Building workflow images..."
docker build -t workflow-main       -f functions/main/Dockerfile       .
docker build -t workflow-montecarlo -f functions/montecarlo/Dockerfile .

WORKFLOW_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
REDIS_KEY="montecarlo-main-$WORKFLOW_ID"

echo ""
echo "==> Writing args to Redis key: $REDIS_KEY"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$REDIS_KEY" '{"n": 50, "generations": 10}'

echo ""
echo "==> Starting main (workflow_id=$WORKFLOW_ID)..."
docker run --rm \
  --network host \
  -e REDIS_HOST="$REDIS_HOST" \
  -e REDIS_PORT="$REDIS_PORT" \
  -e WORKFLOW_NAME="montecarlo" \
  -e WORKFLOW_ID="$WORKFLOW_ID" \
  -e INSTANCE_ID="$WORKFLOW_ID" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  workflow-main \
  "$REDIS_KEY"
