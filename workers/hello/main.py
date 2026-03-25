import os

import redis


def main():
    deployment_id = os.environ["DEPLOYMENT_ID"]
    redis_host = os.environ.get("REDIS_HOST", "redis.swarmopt.svc.cluster.local")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    stream = f"test_workflow_{deployment_id}"

    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    r.xadd(stream, {"message": "hello_world"})
    print(f"wrote hello_world to {stream}")


if __name__ == "__main__":
    main()
