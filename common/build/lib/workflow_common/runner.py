"""
Worker entrypoint. Pops one task from TASK_QUEUE, calls main(**inputs),
pushes the result dict to workflow:results:{call_id}, then exits.
"""
import json
import os
import sys

sys.path.insert(0, "/app/src")

import redis as redis_lib


def run() -> None:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    task_queue = os.environ.get("TASK_QUEUE")

    if not task_queue:
        print("TASK_QUEUE env var is required", file=sys.stderr)
        sys.exit(1)

    r = redis_lib.Redis(host=host, port=port, decode_responses=True)

    result = r.blpop(task_queue, timeout=60)
    if result is None:
        print(f"timed out waiting on {task_queue}", file=sys.stderr)
        sys.exit(1)

    _, raw = result
    task = json.loads(raw)
    call_id = task["call_id"]
    inputs = task["inputs"]

    from main import main
    output = main(**inputs)

    r.rpush(f"workflow:results:{call_id}", json.dumps(output))


if __name__ == "__main__":
    run()
