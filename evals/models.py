"""Reference data for one equipment evaluation, kept separate from the agent input."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

RubricQuestion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvalModel(BaseModel, frozen=True, extra="forbid"):
    """Immutable records can be shared by cases in the same comparison."""


class EmployeeRequest(EvalModel):
    employee_id: str
    request: str


class Issue(EvalModel):
    item: str
    issued: date | None
    assigned: bool


class Fixture(EvalModel):
    as_of: date
    role: str | None
    hired: date
    issues: tuple[Issue, ...]


class Expected(EvalModel):
    item: str
    item_aliases: tuple[str, ...] = ()
    decision: Literal["approve", "deny", "human_review"]
    reason: str
    next_eligible_date: date | None = None
    rubric: dict[str, RubricQuestion] = Field(min_length=1)


class EvalCase(EvalModel):
    id: str
    group: str
    input: EmployeeRequest
    fixture: Fixture
    expected: Expected
