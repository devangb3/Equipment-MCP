from dataclasses import dataclass
from datetime import date
from typing import Literal

Intent = Literal["routine", "additional", "broken", "unclear"]


@dataclass(frozen=True)
class Eligibility:
    decision: Literal["approve", "deny", "human_review"]
    reason: str
    submitted: date
    next_eligible_date: date | None = None


@dataclass(frozen=True)
class Receipt:
    request_id: int
    eligibility: Eligibility
    review_id: str | None
