"""SQLite models for the original submission and its optional human decision."""

from datetime import date, datetime
from typing import Literal

from sqlalchemy import String, text
from sqlmodel import Field, Session, SQLModel

from .errors import ReviewAlreadyResolved, UnknownReview
from .requests import Eligibility, Intent, Receipt


class SubmittedRequest(SQLModel, table=True):
    __tablename__ = "submitted_request"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: str
    request: str
    item: str | None
    intent: Intent | None = Field(sa_type=String)
    submitted: date
    policy_outcome: Literal["approve", "deny", "human_review"] = Field(sa_type=String)
    reason: str
    next_eligible_date: date | None

    @classmethod
    def record(
        cls,
        session: Session,
        employee_id: str,
        request: str,
        item: str | None,
        intent: Intent | None,
        outcome: Eligibility,
    ) -> Receipt:
        row = cls(
            employee_id=employee_id,
            request=request,
            item=item,
            intent=intent,
            submitted=outcome.submitted,
            policy_outcome=outcome.decision,
            reason=outcome.reason,
            next_eligible_date=outcome.next_eligible_date,
        )
        session.add(row)
        session.flush()
        assert row.id is not None
        review_id = f"R{row.id}" if row.policy_outcome == "human_review" else None
        return Receipt(request_id=row.id, eligibility=outcome, review_id=review_id)


class ReviewDecision(SQLModel, table=True):
    __tablename__ = "review_decision"

    request_id: int = Field(primary_key=True, foreign_key="submitted_request.id")
    decision: Literal["approve", "deny"] = Field(sa_type=String)
    reviewer: str
    rationale: str
    decided_at: datetime | None = Field(
        default=None,
        nullable=False,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )

    @classmethod
    def record(
        cls,
        session: Session,
        review_id: str,
        decision: Literal["approve", "deny"],
        reviewer: str,
        rationale: str,
    ) -> None:
        submission = session.get(SubmittedRequest, review_id[1:])
        if submission is None or submission.policy_outcome != "human_review":
            raise UnknownReview(f"Unknown review: {review_id}")
        request_id = submission.id
        assert request_id is not None
        prior = session.get(cls, request_id)
        if prior is not None:
            if (prior.decision, prior.reviewer, prior.rationale) == (
                decision,
                reviewer,
                rationale,
            ):
                return
            raise ReviewAlreadyResolved(f"{review_id} already has a recorded decision")
        session.add(
            cls(
                request_id=request_id,
                decision=decision,
                reviewer=reviewer,
                rationale=rationale,
            )
        )
