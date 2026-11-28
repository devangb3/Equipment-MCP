import json

from evals.cases import CASES_BY_ID
from evals.checks import Run, acceptable_reasons, checks
from evals.models import Expected


def test_acceptable_reasons_includes_alias_policy_reason() -> None:
    expected = Expected(
        item="Tablet",
        item_aliases=("drawing tablet",),
        decision="human_review",
        reason="No tablet policy for Manager",
        rubric={"requested_tablet": "Does the agent evaluate the alias?"},
    )

    assert "No drawing tablet policy for Manager" in acceptable_reasons(expected)


def test_unsupported_drawing_tablet_alias_trace_passes_checks() -> None:
    case = CASES_BY_ID["unsupported"]
    alias_reason = "No drawing tablet policy for Manager"
    request = case.input
    calls = [
        (
            "get_employee_info",
            {"employee_id": case.input.employee_id},
            {"role": case.fixture.role, "hired": case.fixture.hired.isoformat()},
        ),
        (
            "get_policy_limits",
            {"role": case.fixture.role},
            {"laptop": 2, "monitor": 3},
        ),
        (
            "check_request_eligibility",
            {
                "employee_id": case.input.employee_id,
                "item": "drawing tablet",
            },
            {
                "decision": "human_review",
                "reason": alias_reason,
                "next_eligible_date": None,
            },
        ),
        (
            "flag_for_human_review",
            {
                "employee_id": case.input.employee_id,
                "request": request.request,
                "reason": alias_reason,
            },
            {"result": "R317"},
        ),
    ]
    trace: list[str] = []
    for tool, arguments, observation in calls:
        trace.extend(
            [
                f"Thought: Check the request.\nAction: {tool} {json.dumps(arguments)}",
                f"Observation: {json.dumps(observation)}",
            ]
        )
    run = Run(
        id=case.id,
        input=request,
        final="Referred for human review under R317 because there is no drawing tablet policy for Managers.",
        trace=trace,
        new_requests=[
            {
                "employee_id": case.input.employee_id,
                "request": request.request,
                "policy_reason": alias_reason,
                "status": "pending_review",
                "review_id": "R317",
            }
        ],
    )

    assert checks(run, case) == {
        "tools": True,
        "database": True,
        "receipt_in_response": True,
    }