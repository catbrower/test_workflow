import inspect
import json
import os
import sys
import time

import redis as redis_lib

_redis_client = None

DELETE_ARGS_KEYS = False


def _log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", file=sys.stderr, flush=True)


def _redis():
    global _redis_client
    if _redis_client is None:
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        _redis_client = redis_lib.Redis(host=host, port=port, decode_responses=True)
    return _redis_client


def _workflow_name() -> str:
    return os.environ.get("WORKFLOW_NAME", "workflow")


def function(fn):
    fn.__workflow_function__ = True
    return fn


def build_work_item_descriptor(fn) -> dict:
    inputs = []
    for name, param in inspect.signature(fn).parameters.items():
        entry = {"name": name}
        if param.annotation != inspect.Parameter.empty:
            entry["type"] = param.annotation.__name__
        if param.default != inspect.Parameter.empty:
            entry["default"] = param.default
        inputs.append(entry)
    return {"function": fn.__name__, "inputs": inputs}


def read_args(key: str) -> dict:
    r = _redis()
    raw = r.get(key)
    if raw is None:
        raise KeyError(f"no args found at Redis key '{key}'")
    if DELETE_ARGS_KEYS:
        r.delete(key)
    return json.loads(raw)


def write_result(result: dict) -> None:
    instance_id = os.environ["INSTANCE_ID"]
    workflow = _workflow_name()
    result_stream = f"{workflow}-return-{instance_id}"
    _redis().xadd(result_stream, {"data": json.dumps(result)})
    _log("write_result", f"wrote to stream {result_stream}")


def call(name: str, **kwargs) -> dict:
    r = _redis()
    instance_id = os.environ["INSTANCE_ID"]
    workflow_id = os.environ["WORKFLOW_ID"]
    workflow = _workflow_name()
    args_key = f"{workflow}-{name}-{instance_id}"
    result_stream = f"{workflow}-return-{instance_id}"

    # Reuse existing result on retry
    existing = r.xread({result_stream: "0-0"}, count=1)
    if existing:
        _log(f"call:{name}", f"found existing result on {result_stream}, reusing")
        return json.loads(existing[0][1][0][1]["data"])

    r.set(args_key, json.dumps(kwargs))
    _log(f"call:{name}", f"wrote args to {args_key}")

    import docker
    try:
        client = docker.from_env()
        container = client.containers.run(
            f"workflow-{name}",
            command=[args_key],
            environment={
                "REDIS_HOST": os.environ.get("REDIS_HOST", "localhost"),
                "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
                "WORKFLOW_NAME": workflow,
                "INSTANCE_ID": instance_id,
                "WORKFLOW_ID": workflow_id,
            },
            detach=True,
            auto_remove=True,
            network_mode="host",
        )
        _log(f"call:{name}", f"container started: {container.short_id}")
    except Exception as e:
        _log(f"call:{name}", f"ERROR spawning container: {e}")
        raise

    start = time.time()
    while True:
        result = r.xread({result_stream: "0-0"}, count=1, block=5000)
        if result:
            _log(f"call:{name}", "received result")
            return json.loads(result[0][1][0][1]["data"])
        elapsed = time.time() - start
        _log(f"call:{name}", f"waiting for result... ({elapsed:.0f}s)")
        if elapsed > 60:
            raise TimeoutError(f"worker '{name}' timed out after 60s")
