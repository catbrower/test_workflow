"""
Docker entrypoint for FlowFunction execution.

Reads a serialized WorkItem from the WORK_ITEM env var and invokes the single
class in main.py decorated with @flow_function. The function is responsible for
writing its own result to Redis when complete.
"""

import inspect
import json
import os
import sys

import main as flow_module
from swarm_opt.model import WorkItem


def _find_flow_function() -> type:
    decorated = [
        cls
        for _, cls in inspect.getmembers(flow_module, inspect.isclass)
        if getattr(cls, "__flow_function__", False)
    ]

    if len(decorated) != 1:
        raise RuntimeError(
            f"expected exactly one class decorated with @flow_function in main.py, "
            f"found {len(decorated)}: {[c.__name__ for c in decorated]}"
        )

    return decorated[0]


def run() -> None:
    raw = os.environ.get("WORK_ITEM")
    if not raw:
        print("error: WORK_ITEM env var is required", file=sys.stderr)
        sys.exit(1)

    work_item = WorkItem.from_dict(json.loads(raw))

    try:
        cls = _find_flow_function()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    cls()._invoke(work_item)


if __name__ == "__main__":
    run()
