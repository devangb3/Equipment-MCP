import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from evals.cases import CASES_BY_ID
from evals.checks import Run
from evals.judge import grade


@pytest.fixture
def referral() -> Run:
    case = CASES_BY_ID["identity"]
    reason = case.expected.reason
    request = case.input
    final = (
        "Referred for human review under R42 because employee E93 could not be found."
    )
    calls = [
        ("get_employee_info", {"employee_id": "E93"}, {"error": reason}),
        (
            "check_request_eligibility",
            {"employee_id": "E93", "item": "monitor"},
            {
                "decision": "human_review",
                "reason": reason,
                "next_eligible_date": None,
            },
        ),
        (
            "flag_for_human_review",
            {"employee_id": "E93", "request": request.request, "reason": reason},
            {"result": "R42"},
        ),
    ]
    trace = []
    for tool, arguments, observation in calls:
        trace.extend(
            [
                f"Thought: Check the request.\nAction: {tool} {json.dumps(arguments)}",
                f"Observation: {json.dumps(observation)}",
            ]
        )
    return Run(
        id=case.id,
        input=request,
        final=final,
        trace=trace,
        new_requests=[
            {
                "employee_id": "E93",
                "request": request.request,
                "policy_reason": reason,
                "status": "pending_review",
                "review_id": "R42",
            }
        ],
    )


def judge_reply(text: str) -> AsyncMock:
    return AsyncMock(
        return_value=[
            {"type": "message", "content": [{"type": "output_text", "text": text}]}
        ]
    )


def verdict(response_passes: bool = True, receipt_passes: bool = True) -> str:
    return json.dumps(
        {
            "response": {
                "passed": response_passes,
                "evidence": "Compared the final referral with the observed R42.",
            },
            "grounding": {
                "passed": True,
                "evidence": "Employee lookup for E93 failed.",
            },
            "case_rubric": {
                "submitted_identity": {
                    "passed": True,
                    "evidence": "The agent looked up E93 and made no role lookup.",
                },
                "receipt_provenance": {
                    "passed": receipt_passes,
                    "evidence": (
                        "The final answer cites the returned R42."
                        if receipt_passes
                        else "The final answer also presents the old R41 as current."
                    ),
                },
            },
        }
    )


def test_grounded_capture_passes_both_graders(referral: Run) -> None:
    respond = judge_reply(verdict())

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert result.passed


def test_semantic_failure_overrides_passing_tool_checks(referral: Run) -> None:
    referral.final = f"{referral.final} Your monitor will ship Friday."
    respond = judge_reply(verdict(response_passes=False))

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert not result.passed


def test_case_rubric_failure_overrides_passing_shared_checks(referral: Run) -> None:
    referral.final = f"{referral.final} R41 also identifies this review."
    respond = judge_reply(verdict(receipt_passes=False))

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert (all(result.checks.values()), result.passed) == (True, False)


def test_judge_receives_named_case_questions(referral: Run) -> None:
    case = CASES_BY_ID["identity"]
    respond = judge_reply(verdict())

    asyncio.run(grade(case, referral, respond, "judge"))
    last_call = respond.await_args_list[-1]
    packet = json.loads(last_call.args[1][0]["content"])

    assert packet["rubric"]["case"] == case.expected.rubric


def test_favorable_judge_cannot_override_wrong_receipt(referral: Run) -> None:
    referral.final = (
        "Your case is R421 because the employee record could not be verified."
    )
    respond = judge_reply(verdict())

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert not result.passed


def test_incomplete_capture_skips_judge(referral: Run) -> None:
    referral.error = "Agent reached its turn limit."
    respond = judge_reply(verdict())

    asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    respond.assert_not_awaited()


@pytest.mark.parametrize("reply", ["CONFIRM", '{"response": {"passed": true}}'])
def test_malformed_verdict_reports_grading_error(referral: Run, reply: str) -> None:
    respond = judge_reply(reply)

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert result.error is not None


@pytest.mark.parametrize("extra_id", [None, "unknown_criterion"])
def test_missing_or_unexpected_case_answer_reports_error(
    referral: Run, extra_id: str | None
) -> None:
    reply = json.loads(verdict())
    if extra_id is None:
        del reply["case_rubric"]["receipt_provenance"]
    else:
        reply["case_rubric"][extra_id] = reply["case_rubric"]["receipt_provenance"]
    respond = judge_reply(json.dumps(reply))

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert result.error and "Case rubric answers do not match" in result.error
