"""Exercise the real MCP/SQLite stack with offline Foundry Responses fixtures."""

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from agent.__main__ import run
from agent.foundry import Item
from agent.refinement import FEEDBACK, REVISE


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
