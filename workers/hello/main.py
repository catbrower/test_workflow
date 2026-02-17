import os
import json
import time
import redis
from datetime import datetime


def now():
    return datetime.utcnow().isoformat() + "Z"


def main():
    # ---- Execution Context (injected by scheduler) ----
    execution_id = os.environ["EXECUTION_ID"]
    node_id = os.environ["NODE_ID"]

    redis_host = os.environ.get("REDIS_HOST", "redis")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))

    # Logical stream names resolved by scheduler
    output_stream = os.environ["OUTPUT_STREAM_greeting"]
    events_stream = os.environ["EVENTS_STREAM"]

    # Params passed as JSON blob
    params = json.loads(os.environ.get("TASK_PARAMS", "{}"))
    name = params.get("name", "World")

    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    # ---- Emit START event ----
    r.xadd(
        events_stream,
        {
            "type": "task.started",
            "execution_id": execution_id,
            "node_id": node_id,
            "timestamp": now()
        }
    )

    # ---- Do Work ----
    greeting = f"Hello, {name}!"
    time.sleep(1)  # simulate work

    # ---- Emit Output ----
    r.xadd(
        output_stream,
        {
            "execution_id": execution_id,
            "node_id": node_id,
            "timestamp": now(),
            "payload": json.dumps({
                "greeting": greeting
            })
        }
    )

    # ---- Emit COMPLETE event ----
    r.xadd(
        events_stream,
        {
            "type": "task.completed",
            "execution_id": execution_id,
            "node_id": node_id,
            "timestamp": now(),
            "status": "success"
        }
    )

    print(greeting)


if __name__ == "__main__":
    main()
