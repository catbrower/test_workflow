import json
import uuid
import redis
import docker

REDIS_HOST = "localhost"
REDIS_PORT = 6379
WORKFLOW_NAME = "montecarlo"

instance_id = str(uuid.uuid4())
args_key = f"{WORKFLOW_NAME}-montecarlo-{instance_id}"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
r.set(args_key, json.dumps({"n": 50}))
print(f"wrote args to: {args_key}")

client = docker.from_env()
container = client.containers.run(
    "workflow-montecarlo",
    command=[args_key],
    environment={
        "REDIS_HOST": REDIS_HOST,
        "REDIS_PORT": str(REDIS_PORT),
        "WORKFLOW_NAME": WORKFLOW_NAME,
        "INSTANCE_ID": instance_id,
        "WORKFLOW_ID": instance_id,
    },
    network_mode="host",
    detach=True,
    auto_remove=False,
)
print(f"container started: {container.short_id}")

exit_code = container.wait()
logs = container.logs().decode()
print(f"exit code: {exit_code['StatusCode']}")
print(f"logs:\n{logs}")
container.remove()

result_stream = f"{WORKFLOW_NAME}-return-{instance_id}"
entries = r.xrange(result_stream)
print(f"result stream {result_stream}:")
for entry_id, fields in entries:
    print(json.dumps(json.loads(fields["data"]), indent=2))
