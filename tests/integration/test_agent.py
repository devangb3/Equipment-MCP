"""Exercise the real MCP/SQLite stack with offline Foundry Responses fixtures."""

import json
import sqlite3
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.server.fastmcp import FastMCP

from agent.__main__ import run
from agent.foundry import Foundry, Item
from agent.refinement import FEEDBACK, REVISE
from evals import run as eval_run
from evals.cases import CASES_BY_ID
from evals.judge import INSTRUCTIONS as JUDGE_INSTRUCTIONS


def message(text: str) -> list[Item]:
    return [{"type": "message", "content": [{"type": "output_text", "text": text}]}]


class FixtureModel:
    def __init__(self, item: str, intent: str) -> None:
        self.item = item
        self.intent = intent

    async def respond(
        self, instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        if instructions in (FEEDBACK, REVISE):
            context = json.loads(str(history[0]["content"]))
            attempt = context["attempts"][-1]
            verified = context["verified_decision"]
            if instructions == REVISE:
                return message(verified)
            if attempt["draft"] == verified:
                return message("CONFIRM")
            return message(f"Remove the shipping promise and report the tool decision: {verified}")
        request = json.loads(str(history[0]["content"]))
        last = history[-1]
        observation = json.loads(str(last.get("output", "{}")))
        if last.get("type") == "function_call_output":
            previous = history[-2]["name"]
        else:
            previous = None
        if previous is None:
            name, args = "get_employee_info", {"employee_id": request["employee_id"]}
        elif previous == "get_employee_info" and "role" in observation:
            name, args = "get_policy_limits", {"role": observation["role"]}
        elif previous in ("get_employee_info", "get_policy_limits"):
            name, args = (
                "check_request_eligibility",
                {
                    "employee_id": request["employee_id"],
                    "item": self.item,
                    "intent": self.intent,
                },
            )
        elif observation.get("decision") == "human_review":
            name, args = (
                "flag_for_human_review",
                {
                    "employee_id": request["employee_id"],
                    "request": request["request"],
                    "reason": observation["reason"],
                },
            )
        elif observation.get("decision") == "approve":
            return message(f"Approved. {observation['reason']}.")
        else:
            return message("Approved. Your equipment ships tomorrow.")
        args["purpose"] = f"Check {name} for this request."
        return [
            {
                "type": "function_call",
                "name": name,
                "call_id": f"c{len(history)}",
                "arguments": json.dumps(args),
            }
        ]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize(
    ("employee", "request_text", "item", "intent", "expected", "reason"),
    [
        (
            "S1",
            "I need my first monitor.",
            "monitor",
            "routine",
            "Approved. First monitor issue.",
            None,
        ),
        ("S1", "Please refresh my laptop.", "laptop", "routine", "Denied.", None),
        (
            "M2",
            "Please refresh my laptop.",
            "laptop",
            "routine",
            "Referred",
            "Missing laptop issue date",
        ),
        (
            "M1",
            "I want to keep my laptop and add another.",
            "laptop",
            "additional",
            "Referred",
            "Additional laptop requested",
        ),
        (
            "X9",
            "I need a monitor.",
            "monitor",
            "routine",
            "Referred",
            "Unknown employee: X9",
        ),
    ],
)
async def test_agent_outcome(
    equipment_url: str,
    tmp_path: Path,
    employee: str,
    request_text: str,
    item: str,
    intent: str,
    expected: str,
    reason: str | None,
) -> None:
    model = FixtureModel(item, intent)
    database = tmp_path / "equipment.sqlite3"
    if expected == "Denied.":
        with sqlite3.connect(database) as db:
            db.execute(
                "UPDATE equipment_issue SET issued=? WHERE employee_id='S1'",
                (f"{date.today().year}-01-01",),
            )

    answer = await run(equipment_url, employee, request_text, model.respond)
    print(f"Final: {answer}")

    with sqlite3.connect(database) as db:
        cases = db.execute(
            "SELECT employee_id, request, reason FROM human_review"
        ).fetchall()
    expected_cases = []
    if reason:
        expected = f"Referred for human review (R1). {reason}."
        expected_cases = [(employee, request_text, reason)]
    elif expected == "Denied.":
        today = date.today()
        # A recent January issue keeps this denial independent of the run date.
        expected = f"Denied. Laptop refresh interval has not elapsed. Next eligible date: {today.year + 4}-01-01."
    assert (answer, cases) == (expected, expected_cases)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("passes", [True, False])
async def test_eval_command_saves_one_graded_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, passes: bool
) -> None:
    case = CASES_BY_ID["ledger-a"]
    model = FixtureModel(case.expected.item, "routine")
    results = tmp_path / "results"
    monkeypatch.setattr(eval_run, "RESULTS", results)
    monkeypatch.setattr(
        sys, "argv", ["evals.run", "run", "--case", case.id, "--judge-model", "judge"]
    )
    monkeypatch.setenv("FOUNDRY_BASE_URL", "https://foundry.example")
    monkeypatch.setenv("FOUNDRY_MODEL", "agent")
    monkeypatch.setenv("FOUNDRY_API_KEY", "test-key")

    async def respond(
        self: Foundry, instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        if instructions != JUDGE_INSTRUCTIONS:
            return await model.respond(instructions, history, tools)
        packet = json.loads(str(history[0]["content"]))
        evidence = packet["capture"]["final"]
        rubric = packet["rubric"]
        verdict = {
            question: {
                "passed": passes if question == "response" else True,
                "evidence": evidence,
            }
            for question in rubric["shared"]
        }
        verdict["case_rubric"] = {
            question: {"passed": True, "evidence": evidence}
            for question in rubric["case"]
        }
        return message(json.dumps(verdict))

    monkeypatch.setattr(Foundry, "respond", respond)

    exit_code = 0
    try:
        await eval_run.main()
    except SystemExit as error:
        exit_code = error.code
    (artifact,) = results.iterdir()
    record = json.loads(artifact.read_text())
    grade = record["grade"]

    assert (
        artifact.suffix,
        record["id"],
        record["trace"][-1],
        grade["model"],
        grade["verdict"]["response"]["evidence"],
        grade["passed"],
        exit_code,
    ) == (
        ".jsonl",
        case.id,
        "Reflection: CONFIRM",
        "judge",
        record["final"],
        passes,
        0 if passes else 1,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize(
    "status", [429, 503, None], ids=["rate-limit", "server-error", "timeout"]
)
async def test_eval_records_foundry_error_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int | None
) -> None:
    first = CASES_BY_ID["ledger-b"]
    second = CASES_BY_ID["ledger-a"]
    agent = Foundry("https://foundry.example/openai/v1/responses", "agent", "test-key")
    fixture = FixtureModel(second.expected.item, "routine")
    fail_next = True

    async def reply(request: httpx.Request) -> httpx.Response:
        nonlocal fail_next
        if fail_next:
            fail_next = False
            if status is None:
                raise httpx.ReadTimeout("Foundry request timed out", request=request)
            return httpx.Response(status)
        body = json.loads(request.content)
        items = await fixture.respond(body["instructions"], body["input"], body["tools"])
        return httpx.Response(200, json={"status": "completed", "output": items})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(reply), **kwargs),
    )
    connect_session = eval_run.create_connected_server_and_client_session

    @asynccontextmanager
    async def session_with_direct_errors(server: FastMCP) -> AsyncGenerator[ClientSession]:
        # Defer the error until after SDK teardown so capture receives it directly.
        async with connect_session(server) as session:
            try:
                yield session
            except httpx.HTTPError as error:
                failure = error
            else:
                return
        raise failure

    monkeypatch.setattr(
        eval_run, "create_connected_server_and_client_session", session_with_direct_errors
    )

    path = tmp_path / "results.jsonl"
    with path.open("w", encoding="utf-8") as output:
        failures = await eval_run.run_cases([first, second], output, agent)

    failed, completed = map(json.loads, path.read_text(encoding="utf-8").splitlines())
    expected_error = str(status) if status is not None else "Foundry request timed out"
    assert (
        failures,
        failed["id"],
        expected_error in failed["error"],
        completed["id"],
        completed["final"],
    ) == (
        1,
        first.id,
        True,
        second.id,
        "Approved. Laptop refresh interval met.",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_failover_after_saved_referral_does_not_create_a_second_case(
    equipment_url: str,
    tmp_path: Path,
) -> None:
    from agent.providers import Failover

    fixture = FixtureModel("laptop", "additional")

    async def primary(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        if any(
            item.get("type") == "function_call_output"
            and '"R1"' in str(item.get("output"))
            for item in history
        ):
            raise httpx.ReadTimeout("primary unavailable after saved referral")
        return await fixture.respond(instructions, history, tools)

    router = Failover(primary, fixture.respond)

    answer = await run(
        equipment_url, "M1", "I want to keep my laptop and add another.", router.respond
    )

    with sqlite3.connect(tmp_path / "equipment.sqlite3") as db:
        count = db.execute("SELECT COUNT(*) FROM human_review").fetchone()[0]
    assert (answer, count, router.using_fallback) == (
        "Referred for human review (R1). Additional laptop requested.",
        1,
        True,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_http_provider_failover_preserves_tool_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.providers import Failover, OpenRouter

    case = CASES_BY_ID["ledger-c"]
    services = eval_run.prepare(case, tmp_path / "equipment.sqlite3")
    fixture = FixtureModel(case.expected.item, "routine")
    provider_calls: list[str] = []

    async def reply(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        provider_calls.append(request.url.host)
        if request.url.host == "foundry.example" and any(
            item.get("type") == "function_call_output"
            and '"R43"' in str(item.get("output"))
            for item in body["input"]
        ):
            return httpx.Response(503)
        output = await fixture.respond(
            body["instructions"], body["input"], body["tools"]
        )
        return httpx.Response(200, json={"status": "completed", "output": output})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(reply), **kwargs),
    )
    primary = Foundry(
        "https://foundry.example/openai/v1/responses", "deployment", "key"
    )
    fallback = OpenRouter("vendor/model", "key")
    router = Failover(primary.respond, fallback.respond)

    result = await eval_run.capture(case, services, router.respond)

    with sqlite3.connect(services.path) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM human_review WHERE id > 42"
        ).fetchone()[0]
    assert (
        result.get("error"),
        result.get("final"),
        count,
        router.using_fallback,
        provider_calls[-1],
    ) == (
        None,
        "Referred for human review (R43). Missing laptop issue date.",
        1,
        True,
        "openrouter.ai",
    )
