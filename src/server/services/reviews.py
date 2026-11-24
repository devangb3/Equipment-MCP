import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..database import history_session
from ..models import (
    Eligibility,
    InvalidField,
    ReviewAlreadyResolved,
    UnknownReview,
    required,
)
from ..models.history import ReviewDecision, SubmittedRequest


@dataclass(frozen=True)
class ReviewQueue:
    path: Path
    today: Callable[[], date] = date.today

    def flag_for_human_review(self, employee_id: str, request: str, reason: str) -> str:
        """Save the original request and escalation reason, including for an unknown employee. Return its review ID."""
        employee_id = required(employee_id, "employee_id")
        required(request, "request")
        required(reason, "reason")
        outcome = Eligibility("human_review", reason, self.today())
        with history_session(self.path) as session:
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
    with history_session(path) as session:
        submission = session.get(SubmittedRequest, review_id[1:])
        if submission is None or submission.policy_outcome != "human_review":
            raise UnknownReview(f"Unknown review: {review_id}")
        request_id = submission.id
        assert request_id is not None
        prior = session.get(ReviewDecision, request_id)
        if prior is not None:
            if (prior.decision, prior.reviewer, prior.rationale) == (
                decision,
                reviewer,
                rationale,
            ):
                return
            raise ReviewAlreadyResolved(f"{review_id} already has a recorded decision")
        session.add(
            ReviewDecision(
                request_id=request_id,
                decision=decision,
                reviewer=reviewer,
                rationale=rationale,
            )
        )
