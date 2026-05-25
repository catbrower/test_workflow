from typing import Iterator

from pydantic import BaseModel

from models import WorkflowFunction
from workflow import flux, function

class MainRequest(BaseModel):
    n: int = 10
    population_size: int = 5
    generations: int = 10


class MainResult(BaseModel):
    generation: int
    pi: float


@function
class Main(WorkflowFunction):
    def main(self, request: MainRequest) -> Iterator[MainResult]:
        for i in range(request.generations):
            results = flux("montecarlo", count=request.population_size, n=request.n)
            avg_pi = sum(r["pi_estimate"] for r in results) / len(results)
            yield MainResult(generation=i, pi=avg_pi)
