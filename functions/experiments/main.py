"""
Demo: WorkItemRedisService

Shows how to write WorkItem, WorkItemResult, and WorkItemDescriptor to Redis
using each of the three IoMode transports.

Requires a running Redis instance at localhost:6379.
Run with: python3 demo_work_item_redis_service.py
"""

import json
from typing import Generic, List, TypeVar, get_type_hints
import yaml
from uuid import uuid4
from pydantic import BaseModel, Field
import logging

from swarm_opt.model import (
    BoundedParameter,
    Declaration,
    IoMode,
    Parameter,
    WorkItem,
    WorkItemDescriptor,
    WorkItemResult,
    WorkOutcome
)
from swarm_opt.service.redis_service import RedisService
from swarm_opt.service.work_item_redis_service import WorkItemRedisService

from model_to_yaml import model_to_yaml, function_to_yaml
from decorators import flow_function

redis = RedisService()
svc = WorkItemRedisService()

InputsT = TypeVar("InputsT", bound=BaseModel)
OutputsT = TypeVar("OutputsT", bound=BaseModel)

class Function(Generic[InputsT, OutputsT]):
    def __init__(self):
        self.log = logging.getLogger(__name__)

    def _invoke(self, work_item: WorkItem) -> None:
        hints = get_type_hints(type(self).main)
        inputs_type = hints["inputs"]
        kwargs = {p.name: p.value for p in getattr(work_item, "inputs", [])}
        try:
            output = self.main(inputs_type(**kwargs))
            outputs = [Parameter.build(name, getattr(output, name)) for name in output.model_fields]
            result = WorkItemResult.success(outputs=outputs)

            WorkItemRedisService().write_work_item_result(
                result, key=work_item.output_key, mode=work_item.output_mode
            )
        except Exception as ex:
            self.log.error(ex)
            result = WorkItemResult.failure(str(ex))

    def main(self, inputs: InputsT) -> OutputsT:
        raise NotImplementedError("not implemented")

class FunctionInputs(BaseModel):
    index: float = Field(ge=-1, lt=1)

class FunctionOutputs(BaseModel):
    result: float = Field(ge=0, le=100)

class FunctionProperties(BaseModel):
    max_iter: int = Field(ge=0, le=1000)

@flow_function(properties=FunctionProperties)
class WorkflowFunction(Function[FunctionInputs, FunctionOutputs]):
    def main(self, inputs: FunctionInputs) -> FunctionOutputs:
        return FunctionOutputs(result=inputs.index ** 2)

def load_descriptor() -> dict:
    descriptor = yaml.safe_load(open("descriptor.yml"))

    if len(descriptor) != 1:
        print("Invalid descripto expected exactly one document")

    descriptor = dict(descriptor.items())

    desc_name = list(descriptor.keys())[0]

    descriptor = descriptor.get(desc_name, {})
    descriptor["name"] = desc_name

    desc_inputs = descriptor.get("inputs", [])
    desc_outputs = descriptor.get("outputs", [])
    desc_properties = descriptor.get("properties", [])
    desc_input_mode = descriptor.get("input_mode", None)
    desc_output_mode = descriptor.get("output_mode", None)

    return descriptor

# TODO the properties list should be set in a redis register and constant throughout all runs. dont pass here, femove from work item
def build_work_item_from_descriptor(inputs: List[Parameter], descriptor: WorkItemDescriptor) -> WorkItem:
    return WorkItem(
        id=uuid4(),
        workflow_id=uuid4(),
        name=descriptor.name,
        inputs=[
            Parameter.build("ticker", "SPY"),
            Parameter.build("lookback_days", 90),
        ],
        input_mode=IoMode.LIST,
        input_key="optimization:task",
        output_mode=IoMode.STREAM,
        output_key=f"optimization:task:{JOB_ID}",
    )

# To be set as env vars
WORKFLOW_NAME = "experiments"
JOB_ID = str(uuid4())

DESCRIPTOR = load_descriptor()


print()


# # ---------------------------------------------------------------------------
# # WorkItem — LIST  (standard queue push, mirrors Java writeInput)
# # ---------------------------------------------------------------------------

# print("--- WorkItem → LIST ---")

# item = WorkItem(
#     id=uuid4(),
#     workflow_id=uuid4(),
#     name="BACKTEST",
#     inputs=[
#         Parameter.build("ticker", "SPY"),
#         Parameter.build("lookback_days", 90),
#     ],
#     properties=[
#         Parameter("mutator.ticker", "randomPick:SPY,AAPL,QQQ", "mutator"),
#     ],
#     input_mode=IoMode.LIST,
#     input_key="optimization:task",
#     output_mode=IoMode.STREAM,
#     output_key=f"optimization:task:{JOB_ID}",
# )

# svc.write_work_item(item)
# print(f"  pushed to list 'optimization:task'")

# raw = redis.lpop("optimization:task")
# print(f"  popped: {json.dumps(json.loads(raw), indent=2)}\n")

# # ---------------------------------------------------------------------------
# # WorkItem — VALUE  (single slot, e.g. hand-off between two components)
# # ---------------------------------------------------------------------------

# print("--- WorkItem → VALUE ---")

# item_v = WorkItem(
#     name="EXPRESSION",
#     inputs=[Parameter.build("expr", "close > sma(20)")],
#     input_mode=IoMode.VALUE,
#     input_key="work:current",
# )

# svc.write_work_item(item_v)
# print(f"  set key 'work:current'")
# print(f"  got:  {redis.get('work:current')}\n")
# redis.delete("work:current")

# # ---------------------------------------------------------------------------
# # WorkItem — STREAM  (append-only audit log / fan-out)
# # ---------------------------------------------------------------------------

# print("--- WorkItem → STREAM ---")

# item_s = WorkItem(
#     name="DATA_READ",
#     inputs=[
#         Parameter.build("collection", "OPTIMIZATION_JOB_REQUEST"),
#         Parameter.build("command", "FIND_ALL"),
#     ],
#     input_mode=IoMode.STREAM,
#     input_key="audit:work-items",
# )

# svc.write_work_item(item_s)
# print(f"  appended to stream 'audit:work-items'")
# entries = redis.stream_range("audit:work-items")
# print(f"  entry fields: {list(entries[0]['data'].keys())}\n")

# # ---------------------------------------------------------------------------
# # WorkItemResult — STREAM  (standard result channel, mirrors Java writeOutput)
# # ---------------------------------------------------------------------------

# print("--- WorkItemResult → STREAM ---")

# result_key = f"optimization:task:{JOB_ID}"
# result = WorkItemResult.success(outputs=[
#     Parameter.build("sharpe_ratio", 1.42),
#     Parameter.build("max_drawdown", -0.08),
# ])

# svc.write_work_item_result(result, key=result_key, mode=IoMode.STREAM)
# print(f"  appended to stream '{result_key}'")
# entries = redis.stream_range(result_key)
# print(f"  outcome: {entries[0]['data']['outcome']}")
# print(f"  outputs: {entries[0]['data']['outputs']}\n")

# # ---------------------------------------------------------------------------
# # WorkItemResult — LIST
# # ---------------------------------------------------------------------------

# print("--- WorkItemResult → LIST ---")

# svc.write_work_item_result(result, key="results:queue", mode=IoMode.LIST)
# raw = redis.lpop("results:queue")
# print(f"  popped outcome: {json.loads(raw)['outcome']}\n")

# # ---------------------------------------------------------------------------
# # WorkItemResult — VALUE  (single-slot result, e.g. latest score)
# # ---------------------------------------------------------------------------

# print("--- WorkItemResult → VALUE ---")

# failure = WorkItemResult.failure("ticker data unavailable")
# svc.write_work_item_result(failure, key="results:latest", mode=IoMode.VALUE)
# raw = redis.get("results:latest")
# print(f"  got: {raw}\n")
# redis.delete("results:latest")

# # ---------------------------------------------------------------------------
# # WorkItemDescriptor — always VALUE
# # ---------------------------------------------------------------------------

# print("--- WorkItemDescriptor → VALUE ---")

# descriptor = WorkItemDescriptor(
#     id=uuid4(),
#     name="BACKTEST",
#     inputs=[
#         BoundedParameter(name="lookback_days", type="int",   value="90",   upper_bound=365, lower_bound=10),
#         BoundedParameter(name="stop_loss",     type="float", value="0.05", upper_bound=0.2, lower_bound=0.01),
#     ],
#     outputs=[
#         Declaration(name="sharpe_ratio", type="float"),
#         Declaration(name="max_drawdown", type="float"),
#     ],
#     input_mode=IoMode.LIST,
#     output_mode=IoMode.STREAM,
# )

# svc.write_work_item_descriptor(descriptor, key="descriptors:BACKTEST")
# print(f"  set key 'descriptors:BACKTEST'")
# raw = redis.get("descriptors:BACKTEST")
# d = json.loads(raw)
# print(f"  name:   {d['name']}")
# print(f"  inputs: {[(i['name'], i['lowerBound'], i['upperBound']) for i in d['inputs']]}")
# print(f"  outputs:{[o['name'] for o in d['outputs']]}\n")
# redis.delete("descriptors:BACKTEST")

# print("Done.")
