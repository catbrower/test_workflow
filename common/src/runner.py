import json
import os
import sys

import main  # noqa: F401 — side effect: registers @function class
from constants import TTL
from decorators import FunctionRegistry
from keys import RedisKeys


def _write_descriptor() -> None:
    descriptor_path = "/app/descriptor.json"
    try:
        with open(descriptor_path) as f:
            descriptor = json.load(f)
    except FileNotFoundError:
        print(f"[runner] no descriptor.json at {descriptor_path}, skipping", file=sys.stderr, flush=True)
        return

    descriptor["instanceId"] = os.environ.get("INSTANCE_ID", "")
    descriptor["workflowId"] = os.environ.get("WORKFLOW_ID", "")
    descriptor["workflowName"] = os.environ.get("WORKFLOW_NAME", "workflow")

    instance_name = descriptor.get("instanceName", "unknown")
    workflow_name = descriptor["workflowName"]
    workflow_id = descriptor["workflowId"]
    hash_key = RedisKeys.descriptor(workflow_name, workflow_id)

    import redis as redis_lib
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    r = redis_lib.Redis(host=host, port=port, decode_responses=True)
    r.hset(hash_key, instance_name, json.dumps(descriptor))
    r.expire(hash_key, TTL)
    print(f"[runner] wrote descriptor to {hash_key}[{instance_name}]", file=sys.stderr, flush=True)


_write_descriptor()
FunctionRegistry.main_function().run()
