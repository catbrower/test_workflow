"""Minimal workflow function: writes one message to the output Redis stream and exits."""

import json
import os

import redis

DEPLOYMENT_ID = os.environ["DEPLOYMENT_ID"]
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

stream = f"test_workflow_{DEPLOYMENT_ID}"
payload = {"message": "hello_world", "deployment_id": DEPLOYMENT_ID}
r.xadd(stream, {"data": json.dumps(payload)})

print(f"[hello] wrote to {stream}: {payload}", flush=True)
