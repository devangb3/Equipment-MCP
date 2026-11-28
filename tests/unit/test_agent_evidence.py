from datetime import date
from typing import Literal

import pytest

from agent.evidence import Evidence
from agent.foundry import AgentError
from server.models.requests import Eligibility

TODAY = date(2026, 5, 10)


def eligibility(decision: Literal["approve", "deny", "human_review"]) -> Eligibility:
    return Eligibility(decision=decision, reason="Policy result.", submitted=TODAY)


def test_draft_before_eligibility_is_rejected() -> None:
    with pytest.raises(AgentError, match="before checking eligibility"):
        Evidence().verified_response()


def test_referral_draft_before_a_confirmed_review_is_rejected() -> None:
    evidence = Evidence(eligibility=eligibility("human_review"))

    with pytest.raises(AgentError, match="before a confirmed referral"):
        evidence.verified_response()


def test_decision_before_the_role_policy_is_rejected() -> None:
    evidence = Evidence(eligibility=eligibility("approve"))

    with pytest.raises(AgentError, match="role policy"):
        evidence.verified_response()


def test_denial_without_a_next_eligible_date_is_rejected() -> None:
    evidence = Evidence(eligibility=eligibility("deny"), policy_seen=True)

    with pytest.raises(AgentError, match="next eligible date"):
        evidence.verified_response()


@pytest.mark.parametrize(
    ("role", "requested"),
    [(None, "Manager"), ("Manager", "Standard employee")],
)
def test_policy_lookup_must_use_the_observed_role(
    role: str | None, requested: str
) -> None:
    evidence = Evidence(role=role)

    with pytest.raises(AgentError, match="observed employee role"):
        evidence.bind(
            "get_policy_limits", {"role": requested}, "M1", "Refresh my laptop."
        )


@pytest.mark.parametrize("decision", [None, "approve"])
def test_referral_requires_a_human_review_decision(
    decision: Literal["approve"] | None,
) -> None:
    evidence = Evidence(eligibility=None if decision is None else eligibility(decision))

    with pytest.raises(AgentError, match="human-review eligibility"):
        evidence.bind("flag_for_human_review", {}, "M1", "I need a monitor.")


@pytest.mark.parametrize("receipt", [" ", "", None, 12])
def test_review_without_a_case_id_is_rejected(receipt: object) -> None:
    with pytest.raises(AgentError, match="no case ID"):
        Evidence().record("flag_for_human_review", {"result": receipt})
