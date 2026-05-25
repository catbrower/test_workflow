import json
import random
import sys

from workflow import build_work_item_descriptor, function, read_args, write_result


def _log(msg: str) -> None:
    print(f"[montecarlo] {msg}", file=sys.stderr, flush=True)


@function
def main(n: int = 1000) -> dict:
    _log(f"computing with n={n}")
    inside = sum(
        1 for _ in range(n)
        if random.random() ** 2 + random.random() ** 2 <= 1.0
    )
    result = {"inside": inside, "total": n}
    _log(f"done: {result}")
    return result


def run():
    _log("starting")

    if len(sys.argv) < 2:
        print("usage: run <redis-key>", file=sys.stderr, flush=True)
        sys.exit(1)

    key = sys.argv[1]
    _log(f"args key: {key}")

    desc = build_work_item_descriptor(main)
    _log(f"descriptor: {json.dumps(desc)}")

    args = read_args(key)
    _log(f"args: {args}")

    result = main(**args)
    write_result(result)
    _log("result written, exiting")
