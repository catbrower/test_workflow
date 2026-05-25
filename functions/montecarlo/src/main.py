import random
import sys
from typing import Iterator

from pydantic import BaseModel

from models import WorkflowFunction
from workflow import function


def _log(msg: str) -> None:
    print(f"[montecarlo] {msg}", file=sys.stderr, flush=True)


class MontecarloRequest(BaseModel):
    n: int = 1000


class MontecarloResult(BaseModel):
    inside: int
    total: int
    ratio: float
    pi_estimate: float


@function
class Montecarlo(WorkflowFunction):
    def main(self, request: MontecarloRequest) -> Iterator[MontecarloResult]:
        _log(f"computing with n={request.n}")
        inside = sum(
            1 for _ in range(request.n)
            if random.random() ** 2 + random.random() ** 2 <= 1.0
        )
        ratio = inside / request.n
        _log(f"done: inside={inside} ratio={ratio:.4f} pi_estimate={4 * ratio:.4f}")
        yield MontecarloResult(inside=inside, total=request.n, ratio=ratio, pi_estimate=4 * ratio)

    def run(self) -> None:
        _log("starting")
        super().run()
        _log("result written, exiting")
