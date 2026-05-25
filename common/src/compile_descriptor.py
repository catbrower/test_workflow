#!/usr/bin/env python3
"""Build-time script: introspects the @function class in main.py and writes descriptor.json."""
import inspect
import json
import sys
import typing

sys.path.insert(0, "/app")
sys.path.insert(0, "/function/src")

import main as _  # noqa: F401, E402 — triggers @function decorator
from decorators import FunctionRegistry  # noqa: E402
from pydantic import BaseModel  # noqa: E402


def _param_entry(name, param):
    entry = {"name": name}
    if param.annotation != inspect.Parameter.empty:
        entry["type"] = getattr(param.annotation, "__name__", str(param.annotation))
    if param.default != inspect.Parameter.empty:
        entry["value"] = param.default
    return entry


def _outputs_from_return_type(fn) -> list:
    hints = typing.get_type_hints(fn)
    return_annotation = hints.get("return")
    if return_annotation is None:
        return []
    type_args = typing.get_args(return_annotation)
    if not type_args:
        return []
    output_cls = type_args[0]
    if not (isinstance(output_cls, type) and issubclass(output_cls, BaseModel)):
        return []
    return [
        {
            "name": field_name,
            "type": getattr(field_info.annotation, "__name__", str(field_info.annotation)),
        }
        for field_name, field_info in output_cls.model_fields.items()
    ]


def generate(output_path: str) -> None:
    cls = FunctionRegistry.main_function
    if cls is None:
        print("no @function class found in main.py", file=sys.stderr)
        sys.exit(1)

    inputs = [
        _param_entry(name, param)
        for name, param in inspect.signature(cls.main).parameters.items()
        if name != "self"
    ]

    props_cls = getattr(cls, "__properties__", None)
    properties = (
        [
            _param_entry(name, param)
            for name, param in inspect.signature(props_cls.__init__).parameters.items()
            if name != "self"
        ]
        if props_cls is not None
        else []
    )

    descriptor = {
        "instanceName": cls.__name__.lower(),
        "inputs": inputs,
        "outputs": _outputs_from_return_type(cls.main),
        "inputMode": "VALUE",
        "outputMode": "STREAM",
    }
    if properties:
        descriptor["properties"] = properties

    with open(output_path, "w") as f:
        json.dump(descriptor, f, indent=2)

    print(f"[compile_descriptor] wrote {output_path}", file=sys.stderr, flush=True)
    print(json.dumps(descriptor, indent=2), file=sys.stderr, flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: compile_descriptor.py <output.json>", file=sys.stderr)
        sys.exit(1)
    generate(sys.argv[1])
