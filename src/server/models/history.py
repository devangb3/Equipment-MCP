"""SQLite models for the original submission and its optional human decision."""

from datetime import date, datetime
from typing import Literal

from sqlalchemy import String, text
from sqlmodel import Field, Session, SQLModel

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
        return Receipt(row.id, outcome, review_id)


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
