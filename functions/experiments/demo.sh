#!/usr/bin/env bash
set -euo pipefail

IMAGE="flow-function-runner:latest"
REDIS_HOST="${REDIS_HOST:-redis.swarmopt.svc.cluster.local}"
REDIS_PORT="${REDIS_PORT:-6379}"
OUTPUT_KEY="return-WorkflowFunction-2b4efc23-3454-4694-9aff-ae72bb71a55e"

# Build the image
echo "==> Building $IMAGE ..."
docker build -t "$IMAGE" "$(dirname "$0")"

# Construct the WorkItem JSON.
# name     — must match a Function subclass class name in main.py
# inputs   — each field in FunctionInputs as {name, type, value}
# outputMode / outputKey — where WorkItemResult is written in Redis
WORK_ITEM=$(cat <<EOF
{
  "id": "f3e09c56-efe7-4e2f-ab6c-22cf2f670165",
  "workflow_id": "2b4efc23-3454-4694-9aff-ae72bb71a55e",
  "name": "WorkflowFunction",
  "inputs": [
    {"name": "index", "type": "float", "value": "0.5"}
  ],
  "outputMode": "STREAM",
  "outputKey": "return-WorkflowFunction-2b4efc23-3454-4694-9aff-ae72bb71a55e"
}
EOF
)

echo ""
echo "==> Running WorkflowFunction with WorkItem:"
echo "$WORK_ITEM" | python3 -m json.tool 2>/dev/null || echo "$WORK_ITEM"
echo ""

docker run --rm \
  --network host \
  -e WORK_ITEM="$WORK_ITEM" \
  -e REDIS_HOST="$REDIS_HOST" \
  -e REDIS_PORT="$REDIS_PORT" \
  "$IMAGE"

echo ""
echo "==> Result written to Redis stream: $OUTPUT_KEY"
echo "    Read it with:"
echo "    redis-cli -h $REDIS_HOST -p $REDIS_PORT XRANGE $OUTPUT_KEY - +"

# KEYS *
# XREAD STREAMS stream_key 0-0
# DEL streak_key
