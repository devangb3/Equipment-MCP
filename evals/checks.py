"""Score tool use and review records in captured evaluation traces."""

import argparse
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

from .cases import CASES_BY_ID
from .models import EmployeeRequest, EvalCase, Expected

OBSERVATION = TypeAdapter(dict[str, object])


class Call(BaseModel):
    name: str
    arguments: dict[str, str]
    observation: dict[str, object] = Field(default_factory=dict)


class Run(BaseModel):
    id: str
    input: EmployeeRequest | None = None
    final: str | None = None
    error: str | None = None
    trace: list[str]
    new_requests: list[dict[str, object]]

    def calls(self) -> list[Call]:
        calls = []
        for entry in self.trace:
            if "\nAction: " in entry:
                name, args = entry.split("\nAction: ", 1)[1].split(" ", 1)
                calls.append(Call(name=name, arguments=json.loads(args)))
            elif entry.startswith("Observation: ") and calls:
                calls[-1].observation = OBSERVATION.validate_json(
                    entry.removeprefix("Observation: ")
                )
        return calls


def acceptable_reasons(expected: Expected) -> frozenset[str]:
    reasons = {expected.reason}
    if not expected.item_aliases:
        return frozenset(reasons)
    pattern = re.compile(re.escape(expected.item), re.IGNORECASE)
    for alias in expected.item_aliases:
        reasons.add(pattern.sub(alias, expected.reason))
    return frozenset(reasons)


def checks(run: Run, case: EvalCase) -> dict[str, bool]:
    gold = case.expected
    items = {gold.item, *gold.item_aliases}
    reasons = acceptable_reasons(gold)
    calls = run.calls()
    eligibility = [c for c in calls if c.name == "check_request_eligibility"]
    roles = [c.arguments.get("role") for c in calls if c.name == "get_policy_limits"]
    tools_ok = bool(
        eligibility
        and eligibility[-1].arguments.get("item", "").casefold() in items
        and eligibility[-1].observation.get("decision") == gold.decision
        and eligibility[-1].observation.get("reason") in reasons
        and eligibility[-1].observation.get("next_eligible_date")
        == (gold.next_eligible_date.isoformat() if gold.next_eligible_date else None)
        and any(c.name == "get_employee_info" for c in calls)
        and all(
            c.arguments.get("employee_id") == case.input.employee_id
            for c in calls
            if c.name != "get_policy_limits"
        )
        and (set(roles) == {case.fixture.role} if case.fixture.role else not roles)
    )
    rows = run.new_requests
    referrals = [c for c in calls if c.name == "flag_for_human_review"]
    database_ok = not rows and not referrals
    if gold.decision == "human_review":
        database_ok = (
            len(rows) == len(referrals) == 1
            and rows[0].get("status") == "pending_review"
            and rows[0].get("request") == case.input.request
            and rows[0].get("employee_id") == case.input.employee_id
            and rows[0].get("policy_reason") in reasons
            and bool(rows[0].get("review_id"))
            and rows[0].get("review_id") == referrals[0].observation.get("result")
        )
    result = {"tools": tools_ok, "database": database_ok}
    if gold.decision == "human_review":
        receipt = rows[0].get("review_id") if len(rows) == 1 else None
        result["receipt_in_response"] = (
            isinstance(receipt, str)
            and bool(receipt)
            and re.search(rf"(?<!\w){re.escape(receipt)}(?!\w)", run.final or "")
            is not None
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", type=Path)
    for line in parser.parse_args().captures.read_text().splitlines():
        run = Run.model_validate_json(line)
        print(
            json.dumps(
                {
                    "id": run.id,
                    "checks": checks(run, CASES_BY_ID[run.id]),
                }
            )
        )


if __name__ == "__main__":
    main()
