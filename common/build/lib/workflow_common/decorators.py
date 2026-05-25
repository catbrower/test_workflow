from __future__ import annotations

from typing import Optional, Type, TypeVar

from pydantic import BaseModel

F = TypeVar("F")


def flow_function(properties: Optional[Type[BaseModel]] = None):
    """Mark a Function subclass as a flow function.

    Usage:
        @flow_function()
        class MyExperiment:
            ...

        @flow_function(properties=FunctionProperties)
        class MyExperiment:
            ...

        MyExperiment.__properties__   # -> FunctionProperties, or None
        MyExperiment.PropertiesType   # -> TypeVar bound to FunctionProperties, or None
    """
    if properties is not None and not (
        isinstance(properties, type) and issubclass(properties, BaseModel)
    ):
        raise TypeError(
            f"@flow_function(properties=...) requires a BaseModel subclass, got {properties!r}"
        )

    def decorator(target: F) -> F:
        target.__flow_function__ = True
        target.__properties__ = properties
        target.PropertiesType = (
            TypeVar("PropertiesType", bound=properties) if properties is not None else None
        )
        return target

    return decorator
