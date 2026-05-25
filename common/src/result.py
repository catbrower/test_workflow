from __future__ import annotations

import os
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel


class WorkOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TERMINATED = "TERMINATED"
    COMPLETE = "COMPLETE"


class Parameter(BaseModel):
    name: str
    type: str
    value: Any


class WorkItemResult(BaseModel):
    outcome: WorkOutcome
    instance_id: str
    error: Optional[str] = None
    values: Optional[List[Parameter]] = None

    @classmethod
    def complete(cls) -> WorkItemResult:
        return cls(outcome=WorkOutcome.COMPLETE, instance_id=os.environ["INSTANCE_ID"])

    @classmethod
    def success(cls, values: Optional[List[Parameter]] = None) -> WorkItemResult:
        return cls(outcome=WorkOutcome.SUCCESS, instance_id=os.environ["INSTANCE_ID"], values=values)

    @classmethod
    def failure(cls, error: str) -> WorkItemResult:
        return cls(outcome=WorkOutcome.FAILURE, instance_id=os.environ["INSTANCE_ID"], error=error)
