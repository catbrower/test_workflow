#!/usr/bin/env bash
set -euo pipefail

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "==> Building workflow images..."
docker build -t workflow-main       -f functions/main/Dockerfile       .
docker build -t workflow-montecarlo -f functions/montecarlo/Dockerfile .

WORKFLOW_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
REDIS_KEY="montecarlo-main-$WORKFLOW_ID"
RESULT_STREAM="montecarlo-return-$WORKFLOW_ID"

echo ""
echo "==> Writing args: $REDIS_KEY"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$REDIS_KEY" '{"n": 50000, "population_size": 10, "generations": 10}'

echo ""
echo "==> Subscribing to $RESULT_STREAM"

python3 -c "
import redis, json, time, sys
r = redis.Redis(host='$REDIS_HOST', port=int('$REDIS_PORT'), decode_responses=True)
last = '0-0'
deadline = time.time() + 300
while time.time() < deadline:
    res = r.xread({'$RESULT_STREAM': last}, count=10, block=500)
    if res:
        for _, msgs in res:
            for mid, fields in msgs:
                data = json.loads(fields['data'])
                print(json.dumps(data, indent=2), flush=True)
                last = mid
" &
READER_PID=$!

echo "==> Starting main (workflow_id=$WORKFLOW_ID)..."
echo ""
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

sleep 1
kill "$READER_PID" 2>/dev/null || true

echo ""
echo "==> Stream: $RESULT_STREAM"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" XRANGE "$RESULT_STREAM" - +
