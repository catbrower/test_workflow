from __future__ import annotations

from typing import TypeVar


class FunctionRegistry:
    main_function = None


def function(cls=None, *, properties=None):
    """Mark a class as a workflow function and register it.

    Usage:
        @function
        class MyFn(WorkflowFunction): ...

        @function(properties=MyProperties)
        class MyFn(WorkflowFunction): ...
    """
    def decorator(target):
        target.__workflow_function__ = True
        target.__properties__ = properties
        target.PropertiesType = (
            TypeVar("PropertiesType", bound=properties) if properties is not None else None
        )
        FunctionRegistry.main_function = target
        return target

    if cls is not None:
        return decorator(cls)
    return decorator
