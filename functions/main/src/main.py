from typing import Iterator

from pydantic import BaseModel

from models import WorkflowFunction
from workflow import flux, function


class WorkFlowResult(BaseModel):
    generation: int
    pi: float


@function
class Main(WorkflowFunction[WorkFlowResult]):
    def main(self, n: int = 10, population_size: int = 5, generations: int = 10) -> Iterator[WorkFlowResult]:
        for i in range(generations):
            results = flux("montecarlo", count=population_size, n=n)
            avg_pi = sum(r["pi_estimate"] for r in results) / len(results)
            yield WorkFlowResult(generation=i, pi=avg_pi)
