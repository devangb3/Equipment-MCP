import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent.foundry import Foundry, Item
from evals.cases import CASES_BY_ID
from evals.checks import Run
from evals.judge import Finding, grade
from evals.judge import main as grade_captures

PASSING_REFERRAL_CHECKS = {"tools": True, "database": True, "receipt_in_response": True}


@pytest.fixture
def referral() -> Run:
    case = CASES_BY_ID["identity"]
    reason = "Unknown employee: E93"
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
                "evidence": (
                    "The final referral cites the observed R42."
                    if response_passes
                    else "No tool confirmed that the monitor will ship Friday."
                ),
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

    response = result.verdict.response if result.verdict else None
    assert (result.checks, result.error, response, result.passed) == (
        PASSING_REFERRAL_CHECKS,
        None,
        Finding(
            passed=False,
            evidence="No tool confirmed that the monitor will ship Friday.",
        ),
        False,
    )


def test_case_rubric_failure_overrides_passing_shared_checks(referral: Run) -> None:
    referral.final = f"{referral.final} R41 also identifies this review."
    respond = judge_reply(verdict(receipt_passes=False))

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    parsed = result.verdict
    assert (
        result.checks,
        result.error,
        (parsed.response.passed, parsed.grounding.passed) if parsed else None,
        parsed.case_rubric["receipt_provenance"] if parsed else None,
        result.passed,
    ) == (
        PASSING_REFERRAL_CHECKS,
        None,
        (True, True),
        Finding(
            passed=False,
            evidence="The final answer also presents the old R41 as current.",
        ),
        False,
    )


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

    response = result.verdict.response if result.verdict else None
    assert (result.checks, result.error, response, result.passed) == (
        {"tools": True, "database": True, "receipt_in_response": False},
        None,
        Finding(passed=True, evidence="The final referral cites the observed R42."),
        False,
    )


def test_incomplete_capture_skips_judge(referral: Run) -> None:
    referral.error = "Agent reached its turn limit."
    respond = judge_reply(verdict())

    asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    respond.assert_not_awaited()


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        pytest.param(
            "CONFIRM",
            [
                "Unable to grade capture: 1 validation error for Verdict",
                "Invalid JSON: expected value at line 1 column 1",
            ],
            id="non-json-reply",
        ),
        pytest.param(
            '{"response": {"passed": true}}',
            [
                "Unable to grade capture: 3 validation errors for Verdict",
                "response.evidence",
                "Field required",
                "grounding",
                "Field required",
                "case_rubric",
                "Field required",
            ],
            id="incomplete-verdict",
        ),
    ],
)
def test_malformed_verdict_reports_grading_error(
    referral: Run, reply: str, expected: list[str]
) -> None:
    respond = judge_reply(reply)

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    diagnostics = [
        line.partition(" [type=")[0].strip()
        for line in (result.error or "").splitlines()
        if not line.startswith("    ")
    ]
    assert (diagnostics, result.checks, result.verdict, result.passed) == (
        expected,
        PASSING_REFERRAL_CHECKS,
        None,
        False,
    )


@pytest.mark.parametrize(
    ("extra_id", "diagnostic"),
    [
        (None, "missing=['receipt_provenance'], unexpected=[]."),
        ("unknown_criterion", "missing=[], unexpected=['unknown_criterion']."),
    ],
)
def test_missing_or_unexpected_case_answer_reports_error(
    referral: Run, extra_id: str | None, diagnostic: str
) -> None:
    reply = json.loads(verdict())
    if extra_id is None:
        del reply["case_rubric"]["receipt_provenance"]
    else:
        reply["case_rubric"][extra_id] = reply["case_rubric"]["receipt_provenance"]
    respond = judge_reply(json.dumps(reply))

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert (result.error, result.verdict, result.passed) == (
        f"Unable to grade capture: Case rubric answers do not match: {diagnostic}",
        None,
        False,
    )


def test_capture_for_a_different_case_is_not_graded(referral: Run) -> None:
    respond = judge_reply(verdict())

    result = asyncio.run(grade(CASES_BY_ID["unsupported"], referral, respond, "judge"))

    assert (result.error, respond.await_count) == (
        "Capture does not match the reference case and employee input.",
        0,
    )


def test_blank_final_response_is_not_sent_to_the_judge(referral: Run) -> None:
    referral.final = "  "
    respond = judge_reply(verdict())

    result = asyncio.run(grade(CASES_BY_ID["identity"], referral, respond, "judge"))

    assert (result.error, respond.await_count) == ("Missing final response.", 0)


def install_judge(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    async def respond(
        self: Foundry, instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        return [
            {"type": "message", "content": [{"type": "output_text", "text": reply}]}
        ]

    monkeypatch.setattr(Foundry, "respond", respond)
    monkeypatch.setattr(
        Foundry,
        "from_env",
        lambda: Foundry(
            "https://foundry.example/openai/v1/responses", "agent", "test-key"
        ),
    )


def test_judge_command_scores_a_capture(
    referral: Run,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    capture = tmp_path / "captures.jsonl"
    capture.write_text(f"\n{referral.model_dump_json()}\n", encoding="utf-8")
    install_judge(monkeypatch, verdict())
    monkeypatch.setattr(sys, "argv", ["judge", str(capture), "--model", "grader"])

    asyncio.run(grade_captures())

    printed = json.loads(capsys.readouterr().out)
    assert (printed["id"], printed["model"], printed["passed"]) == (
        "identity",
        "grader",
        True,
    )


def test_judge_command_rejects_a_file_with_no_captures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capture = tmp_path / "empty.jsonl"
    capture.write_text("\n", encoding="utf-8")
    install_judge(monkeypatch, verdict())
    monkeypatch.setattr(sys, "argv", ["judge", str(capture)])

    with pytest.raises(SystemExit) as error:
        asyncio.run(grade_captures())

    output = capsys.readouterr()
    assert (error.value.code, output.out, output.err.splitlines()[-1:]) == (
        2,
        "",
        ["judge: error: No captured runs in input."],
    )


def test_judge_command_rejects_an_unknown_capture(
    referral: Run,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    referral.id = "not-a-case"
    capture = tmp_path / "captures.jsonl"
    capture.write_text(f"\n{referral.model_dump_json()}\n", encoding="utf-8")
    install_judge(monkeypatch, verdict())
    monkeypatch.setattr(sys, "argv", ["judge", str(capture)])

    with pytest.raises(SystemExit) as error:
        asyncio.run(grade_captures())

    output = capsys.readouterr()
    assert (error.value.code, output.out, output.err.splitlines()[-1:]) == (
        2,
        "",
        ["judge: error: Invalid capture at line 2: 'not-a-case'"],
    )


def test_judge_command_exits_when_the_capture_fails(
    referral: Run,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    referral.final = f"{referral.final} Your monitor will ship Friday."
    capture = tmp_path / "captures.jsonl"
    capture.write_text(referral.model_dump_json() + "\n", encoding="utf-8")
    install_judge(monkeypatch, verdict(response_passes=False))
    monkeypatch.setattr(sys, "argv", ["judge", str(capture)])

    with pytest.raises(SystemExit) as error:
        asyncio.run(grade_captures())

    printed = json.loads(capsys.readouterr().out)
    assert (
        error.value.code,
        printed["checks"],
        printed["error"],
        printed["verdict"]["response"]["passed"],
        printed["passed"],
    ) == (
        1,
        PASSING_REFERRAL_CHECKS,
        None,
        False,
        False,
    )
