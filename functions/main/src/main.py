import json
import sys

from workflow import build_work_item_descriptor, call, function, read_args


@function
def main(n: int = 10, generations: int = 10) -> dict:
    result = call("montecarlo", n=n)
    return {"n": n, "generations": generations, "worker_result": result}


def run():
    if len(sys.argv) < 2:
        print("usage: run <redis-key>", file=sys.stderr)
        sys.exit(1)

    key = sys.argv[1]

    desc = build_work_item_descriptor(main)
    print(json.dumps(desc, indent=2), file=sys.stderr)

    args = read_args(key)
    result = main(**args)
    print(json.dumps(result, indent=2))
