import json
import sys
from typing import Generic, Iterator, TypeVar

from pydantic import BaseModel

from result import Parameter, WorkItemResult, WorkOutcome
from workflow import build_work_item_descriptor, read_args, write_result

T = TypeVar("T", bound=BaseModel)


def _to_parameters(item: BaseModel) -> list[Parameter]:
    return [
        Parameter(
            name=field_name,
            type=getattr(field_info.annotation, "__name__", str(field_info.annotation)),
            value=getattr(item, field_name),
        )
        for field_name, field_info in item.model_fields.items()
    ]


class WorkflowFunction(Generic[T]):
    def main(self, **kwargs) -> Iterator[T]:
        raise NotImplementedError

    def run(self) -> None:
        if len(sys.argv) < 2:
            print("usage: run <redis-key>", file=sys.stderr, flush=True)
            sys.exit(1)

        key = sys.argv[1]
        desc = build_work_item_descriptor(self.main)
        print(json.dumps(desc), file=sys.stderr, flush=True)

        args = read_args(key)
        for item in self.main(**args):
            if not isinstance(item, BaseModel):
                raise TypeError(f"main() must yield BaseModel instances, got {type(item).__name__}")
            result = WorkItemResult.success(_to_parameters(item))
            write_result(result.model_dump(mode="json"))
        write_result(WorkItemResult.complete().model_dump(mode="json"))
