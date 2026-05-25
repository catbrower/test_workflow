import inspect
import json
import os
import sys

import redis as redis_lib

from constants import DELETE_ARGS_KEYS, TTL
from decorators import function  # noqa: F401 — re-exported for convenience
from keys import RedisKeys

_redis_client = None


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


def build_work_item_descriptor(fn) -> dict:
    inputs = []
    for name, param in inspect.signature(fn).parameters.items():
        if name == "self":
            continue
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
    r = _redis()
    workflow = _workflow_name()
    group_id = os.environ.get("GROUP_ID")
    if group_id:
        stream = RedisKeys.group_result(workflow, group_id)
    else:
        stream = RedisKeys.result(workflow, os.environ["INSTANCE_ID"])
    r.xadd(stream, {"data": json.dumps(result)})
    r.expire(stream, TTL)
    _log("write_result", f"wrote to stream {stream}")


def flux(name: str, count: int, **kwargs) -> list:
    from uuid import uuid4
    import docker

    r = _redis()
    workflow_id = os.environ["WORKFLOW_ID"]
    workflow = _workflow_name()

    group_id = str(uuid4())
    group_stream = RedisKeys.group_result(workflow, group_id)

    try:
        client = docker.from_env()
        for _ in range(count):
            call_instance_id = str(uuid4())
            args_key = RedisKeys.args(workflow, name, call_instance_id)
            r.set(args_key, json.dumps(kwargs), ex=TTL)
            container = client.containers.run(
                f"workflow-{name}",
                command=[args_key],
                environment={
                    "REDIS_HOST": os.environ.get("REDIS_HOST", "localhost"),
                    "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
                    "WORKFLOW_NAME": workflow,
                    "INSTANCE_ID": call_instance_id,
                    "WORKFLOW_ID": workflow_id,
                    "GROUP_ID": group_id,
                },
                detach=True,
                auto_remove=True,
                network_mode="host",
            )
            _log(f"flux:{name}", f"container started: {container.short_id}")
    except Exception as e:
        _log(f"flux:{name}", f"ERROR spawning containers: {e}")
        raise

    results = []
    completed = 0
    last_id = "0-0"

    while completed < count:
        raw = r.xread({group_stream: last_id}, count=10, block=TTL * 1000)
        if not raw:
            raise TimeoutError(f"flux '{name}' timed out after {TTL}s ({completed}/{count} complete)")
        for _, messages in raw:
            for msg_id, fields in messages:
                last_id = msg_id
                entry = json.loads(fields["data"])
                outcome = entry.get("outcome")
                if outcome == "COMPLETE":
                    completed += 1
                    _log(f"flux:{name}", f"worker complete ({completed}/{count})")
                elif outcome == "SUCCESS":
                    results.append({v["name"]: v["value"] for v in entry.get("values") or []})
                elif outcome == "FAILURE":
                    raise RuntimeError(f"worker '{name}' failed: {entry.get('error')}")

    r.delete(group_stream)
    _log(f"flux:{name}", f"deleted group stream {group_stream}")
    return results


def mono(name: str, **kwargs) -> dict:
    from uuid import uuid4
    import docker

    r = _redis()
    workflow_id = os.environ["WORKFLOW_ID"]
    workflow = _workflow_name()

    call_instance_id = str(uuid4())
    args_key = RedisKeys.args(workflow, name, call_instance_id)
    result_stream = RedisKeys.result(workflow, call_instance_id)

    r.set(args_key, json.dumps(kwargs), ex=TTL)
    _log(f"call:{name}", f"args -> {args_key}")

    try:
        client = docker.from_env()
        container = client.containers.run(
            f"workflow-{name}",
            command=[args_key],
            environment={
                "REDIS_HOST": os.environ.get("REDIS_HOST", "localhost"),
                "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
                "WORKFLOW_NAME": workflow,
                "INSTANCE_ID": call_instance_id,
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

    raw = r.xread({result_stream: "0-0"}, count=1, block=TTL * 1000)
    if not raw:
        raise TimeoutError(f"worker '{name}' timed out after {TTL}s")

    entry = json.loads(raw[0][1][0][1]["data"])
    if entry.get("outcome") != "SUCCESS":
        raise RuntimeError(
            f"worker '{name}' returned {entry.get('outcome')}: {entry.get('error')}"
        )
    flat = {v["name"]: v["value"] for v in entry.get("values") or []}
    r.delete(result_stream)
    _log(f"call:{name}", f"deleted result stream {result_stream}")
    return flat
