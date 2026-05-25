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