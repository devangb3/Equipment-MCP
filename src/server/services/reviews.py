import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..database import database_session
from ..models import (
    Eligibility,
    InvalidField,
    required,
)
from ..models.history import ReviewDecision, SubmittedRequest
from ..models.tool_inputs import EmployeeID, RequestText, ReviewReason


@dataclass(frozen=True)
class ReviewQueue:
    path: Path
    today: Callable[[], date] = date.today

    def flag_for_human_review(
        self, employee_id: EmployeeID, request: RequestText, reason: ReviewReason
    ) -> str:
        """Record a direct referral with the original request and reason, and return its review ID.

        Unknown employee IDs are accepted so a reviewer can investigate them.
        """
        employee_id = required(employee_id, "employee_id")
        required(request, "request")
        required(reason, "reason")
        outcome = Eligibility(
            decision="human_review", reason=reason, submitted=self.today()
        )
        with database_session(self.path, write=True) as session:
            receipt = SubmittedRequest.record(
                session, employee_id, request, None, None, outcome
            )
        assert receipt.review_id is not None
        return receipt.review_id


def resolve_review(
    path: Path, review_id: str, decision: str, reviewer: str, rationale: str
) -> None:
    if not re.fullmatch(r"R[1-9][0-9]*", review_id):
        raise InvalidField("Expected a review ID such as R1")
    if decision not in ("approve", "deny"):
        raise InvalidField("Decision must be approve or deny")
    reviewer = required(reviewer, "reviewer")
    rationale = required(rationale, "rationale")
    with database_session(path, write=True) as session:
        ReviewDecision.record(session, review_id, decision, reviewer, rationale)
