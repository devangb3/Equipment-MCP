from datetime import date
from typing import Literal

from sqlmodel import SQLModel

Intent = Literal["routine", "additional", "broken", "unclear"]


class Eligibility(SQLModel, frozen=True):
    decision: Literal["approve", "deny", "human_review"]
    reason: str
    submitted: date
    next_eligible_date: date | None = None


class Receipt(SQLModel, frozen=True):
    request_id: int
    eligibility: Eligibility
    review_id: str | None
