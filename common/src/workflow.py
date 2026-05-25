import inspect
import json
import os
import sys

import redis as redis_lib

from constants import DELETE_ARGS_KEYS, IMAGE_PULL_POLICY, NAMESPACE as _NAMESPACE_DEFAULT, REDIS_HOST_DEFAULT, SERVICE_ACCOUNT, TTL

NAMESPACE = os.environ.get("WORKFLOW_NAMESPACE", _NAMESPACE_DEFAULT)
from decorators import function  # noqa: F401 — re-exported for convenience
from keys import RedisKeys

_redis_client = None
_k8s_client = None


def _log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", file=sys.stderr, flush=True)


def _redis():
    global _redis_client
    if _redis_client is None:
        host = os.environ.get("REDIS_HOST", REDIS_HOST_DEFAULT)
        port = int(os.environ.get("REDIS_PORT", "6379"))
        _redis_client = redis_lib.Redis(host=host, port=port, decode_responses=True)
    return _redis_client


def _workflow_name() -> str:
    return os.environ.get("WORKFLOW_NAME", "workflow")


def _ensure_k8s():
    global _k8s_client
    if _k8s_client is None:
        from kubernetes import config as k8s_config, client as k8s

        _TOKEN_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        _CA_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

        cfg = k8s.Configuration()
        token = None

        if os.path.exists(_TOKEN_FILE):
            # In-cluster: configure manually because k8s Python client v28+ returns
            # an empty auth_settings() dict, so api_key is never applied to requests.
            with open(_TOKEN_FILE) as f:
                token = f.read().strip()
            cfg.host = f"https://{os.environ['KUBERNETES_SERVICE_HOST']}:{os.environ['KUBERNETES_SERVICE_PORT']}"
            cfg.ssl_ca_cert = _CA_FILE
            _log("k8s", f"in-cluster config: host={cfg.host}, token_len={len(token)}")
        else:
            k8s_config.load_kube_config(client_configuration=cfg)
            _log("k8s", "loaded kube config")

        api_client = k8s.ApiClient(configuration=cfg)
        if token:
            api_client.set_default_header("Authorization", f"Bearer {token}")
        _k8s_client = api_client
    return _k8s_client


def _delete_job(name: str, instance_id: str) -> None:
    from kubernetes import client as k8s
    api_client = _ensure_k8s()
    job_name = f"workflow-{name}-{instance_id}"
    try:
        k8s.BatchV1Api(api_client).delete_namespaced_job(
            name=job_name,
            namespace=NAMESPACE,
            body=k8s.V1DeleteOptions(propagation_policy="Background"),
        )
        _log(f"delete:{name}", f"deleted job {job_name}")
    except Exception as e:
        _log(f"delete:{name}", f"could not delete {job_name}: {e}")


def _spawn_job(name: str, args_key: str, env_vars: dict) -> None:
    from kubernetes import client as k8s
    api_client = _ensure_k8s()

    instance_id = env_vars["INSTANCE_ID"]
    job_name = f"workflow-{name}-{instance_id}"

    job = k8s.V1Job(
        metadata=k8s.V1ObjectMeta(name=job_name, namespace=NAMESPACE),
        spec=k8s.V1JobSpec(
            ttl_seconds_after_finished=TTL,
            backoff_limit=0,
            template=k8s.V1PodTemplateSpec(
                spec=k8s.V1PodSpec(
                    restart_policy="Never",
                    service_account_name=SERVICE_ACCOUNT,
                    containers=[
                        k8s.V1Container(
                            name=name,
                            image=f"workflow-{name}:latest",
                            image_pull_policy=IMAGE_PULL_POLICY,
                            args=[args_key],
                            env=[k8s.V1EnvVar(name=k, value=v) for k, v in env_vars.items()],
                        )
                    ],
                )
            ),
        ),
    )
    k8s.BatchV1Api(api_client).create_namespaced_job(namespace=NAMESPACE, body=job)
    _log(f"spawn:{name}", f"created job {job_name}")


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

    r = _redis()
    workflow_id = os.environ["WORKFLOW_ID"]
    workflow = _workflow_name()

    group_id = str(uuid4())
    group_stream = RedisKeys.group_result(workflow, group_id)

    for _ in range(count):
        call_instance_id = str(uuid4())
        args_key = RedisKeys.args(workflow, name, call_instance_id)
        r.set(args_key, json.dumps(kwargs), ex=TTL)
        _spawn_job(name, args_key, {
            "REDIS_HOST": os.environ.get("REDIS_HOST", REDIS_HOST_DEFAULT),
            "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
            "WORKFLOW_NAMESPACE": NAMESPACE,
            "WORKFLOW_NAME": workflow,
            "INSTANCE_ID": call_instance_id,
            "WORKFLOW_ID": workflow_id,
            "GROUP_ID": group_id,
        })

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
                instance_id = entry.get("instance_id")
                if outcome == "COMPLETE":
                    completed += 1
                    _delete_job(name, instance_id)
                    _log(f"flux:{name}", f"worker complete ({completed}/{count})")
                elif outcome == "SUCCESS":
                    results.append({v["name"]: v["value"] for v in entry.get("values") or []})
                elif outcome == "FAILURE":
                    _delete_job(name, instance_id)
                    raise RuntimeError(f"worker '{name}' failed: {entry.get('error')}")
                elif outcome == "TERMINATED":
                    _delete_job(name, instance_id)
                    raise RuntimeError(f"worker '{name}' was terminated")

    r.delete(group_stream)
    _log(f"flux:{name}", f"deleted group stream {group_stream}")
    return results


def mono(name: str, **kwargs) -> dict:
    from uuid import uuid4

    r = _redis()
    workflow_id = os.environ["WORKFLOW_ID"]
    workflow = _workflow_name()

    call_instance_id = str(uuid4())
    args_key = RedisKeys.args(workflow, name, call_instance_id)
    result_stream = RedisKeys.result(workflow, call_instance_id)

    r.set(args_key, json.dumps(kwargs), ex=TTL)
    _spawn_job(name, args_key, {
        "REDIS_HOST": os.environ.get("REDIS_HOST", REDIS_HOST_DEFAULT),
        "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
        "WORKFLOW_NAMESPACE": NAMESPACE,
        "WORKFLOW_NAME": workflow,
        "INSTANCE_ID": call_instance_id,
        "WORKFLOW_ID": workflow_id,
    })
    _log(f"mono:{name}", f"args -> {args_key}")

    raw = r.xread({result_stream: "0-0"}, count=1, block=TTL * 1000)
    if not raw:
        _delete_job(name, call_instance_id)
        raise TimeoutError(f"worker '{name}' timed out after {TTL}s")

    entry = json.loads(raw[0][1][0][1]["data"])
    outcome = entry.get("outcome")
    _delete_job(name, call_instance_id)
    r.delete(result_stream)
    _log(f"mono:{name}", f"deleted result stream {result_stream}")
    if outcome != "SUCCESS":
        raise RuntimeError(f"worker '{name}' returned {outcome}: {entry.get('error')}")
    flat = {v["name"]: v["value"] for v in entry.get("values") or []}
    return flat
