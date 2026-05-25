"""
Convert a Pydantic BaseModel or a Function subclass to YAML descriptor lists.

Each field becomes a list entry with: name, type, and bound constraints
(gt, lt, gte, lte). Missing bounds default to -inf / inf.

Usage:
    from model_to_yaml import model_to_yaml, function_to_yaml
    from main import FunctionInputs, MyFunction

    print(model_to_yaml(FunctionInputs))
    print(function_to_yaml(MyFunction))
"""

from __future__ import annotations

import inspect
import math
from typing import TYPE_CHECKING, Any, Type, get_type_hints

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    from main import Function


# Maps JSON Schema constraint keys to Pydantic Field kwarg names.
_JSON_TO_CONSTRAINT = {
    "exclusiveMinimum": "gt",
    "minimum": "gte",
    "exclusiveMaximum": "lt",
    "maximum": "lte",
}

_LOWER_KEYS = {"gt", "gte"}
_UPPER_KEYS = {"lt", "lte"}


def _model_to_entries(model: Type[BaseModel]) -> list[dict[str, Any]]:
    try:
        schema = model.model_json_schema()
    except AttributeError:
        schema = model.schema()

    props = schema.get("properties", {})
    entries: list[dict[str, Any]] = []

    for field_name, annotation in model.__annotations__.items():
        field_schema = props.get(field_name, {})
        type_name = getattr(annotation, "__name__", str(annotation))

        entry: dict[str, Any] = {"name": field_name, "type": type_name}

        constraints: dict[str, Any] = {}
        for json_key, constraint_key in _JSON_TO_CONSTRAINT.items():
            if json_key in field_schema:
                constraints[constraint_key] = field_schema[json_key]

        if not any(k in constraints for k in _LOWER_KEYS):
            constraints["gt"] = -math.inf
        if not any(k in constraints for k in _UPPER_KEYS):
            constraints["lt"] = math.inf

        entry.update(constraints)
        entries.append(entry)

    return entries

def model_to_yaml(model: Type[BaseModel]) -> str:
    return yaml.dump(
        _model_to_entries(model),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

def function_to_yaml(cls: Type[Function]) -> str:
    """Return a YAML document with inputs, outputs, and properties lists for *cls*.

    *cls* must be a Function subclass with a typed `main(self, inputs: ...) -> ...`
    method. The properties list is derived from the PropertiesType TypeVar set by
    @flow_function(properties=...). If no properties were specified, it is an empty list.
    """
    if not (isinstance(cls, type) and hasattr(cls, "main") and callable(getattr(cls, "main"))):
        raise TypeError(
            f"function_to_yaml() requires a Function subclass with a 'main' method, got {cls!r}"
        )

    hints = get_type_hints(cls.main)
    sig = inspect.signature(cls.main)
    params = [name for name in sig.parameters if name != "self"]

    input_model = hints.get(params[0]) if params else None
    output_model = hints.get("return")
    properties_type = getattr(cls, "PropertiesType", None)
    properties_model = properties_type.__bound__ if properties_type is not None else None

    doc = {
        "inputs": _model_to_entries(input_model) if input_model else [],
        "outputs": _model_to_entries(output_model) if output_model else [],
        "properties": _model_to_entries(properties_model) if properties_model else [],
    }

    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)
