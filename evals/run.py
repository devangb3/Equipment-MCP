"""Validate the gold labels offline or capture real agent trajectories for a judge."""

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import get_args

from mcp.shared.memory import create_connected_server_and_client_session

from agent.__main__ import describe_failure
from agent.client import bind_call, discover
from agent.foundry import AgentError, Foundry, Item
from agent.loop import run_agent_loop
from agent.refinement import Respond
from server.__main__ import create_server
from server.database import connect, initialize
from server.models.requests import Eligibility, Intent
from server.services import EquipmentRequests

from .cases import CASES, CASES_BY_ID
from .models import EvalCase

PRIOR_REQUEST_ID = 42


def prepare(case: EvalCase, path: Path) -> EquipmentRequests:
    initialize(path)
    fixture = case.fixture
    with connect(path) as db:
        if fixture.role:
            db.execute(
                "INSERT INTO employee VALUES (?, ?, ?)",
                (case.input.employee_id, fixture.role, fixture.hired.isoformat()),
            )
        db.executemany(
            "INSERT INTO equipment_issue(employee_id,item,issued,assigned) VALUES (?,?,?,?)",
            [
                (
                    case.input.employee_id,
                    issue.item,
                    issue.issued.isoformat() if issue.issued else None,
                    issue.assigned,
                )
                for issue in fixture.issues
            ],
        )
        db.execute(
            "INSERT INTO submitted_request(id,employee_id,request,reason,submitted) "
            "VALUES (41,'M1','Prior laptop case','Missing issue date','2025-01-01')"
        )
        db.execute(
            "INSERT INTO submitted_request(id,employee_id,request,reason,submitted) "
            "VALUES (?,'M2','Earlier referral','Missing issue date','2025-02-01')",
            (PRIOR_REQUEST_ID,),
        )
    return EquipmentRequests(path, today=lambda: fixture.as_of)


def validate(case: EvalCase, services: EquipmentRequests) -> None:
    gold = case.expected
    expected = Eligibility(
        decision=gold.decision,
        reason=gold.reason,
        submitted=case.fixture.as_of,
        next_eligible_date=gold.next_eligible_date,
    )
    for request_type in get_args(Intent):
        if (
            services.check_request_eligibility(
                case.input.employee_id, gold.item, request_type
            )
            == expected
        ):
            return
    raise ValueError(f"{case.id}: fixture cannot produce {expected}")


async def capture(
    case: EvalCase, services: EquipmentRequests, respond: Respond
) -> Item:
    trace: list[str] = []
    result: Item = {
        "id": case.id,
        "input": case.input.model_dump(),
        "trace": trace,
    }
    try:
        async with create_connected_server_and_client_session(
            create_server(services)
        ) as session:
            result["final"] = await run_agent_loop(
                case.input.employee_id,
                case.input.request,
                respond,
                await discover(session),
                bind_call(session),
                trace.append,
            )
    except (ExceptionGroup, AgentError, ValueError) as error:
        result["error"] = describe_failure(error)
    with connect(services.path) as db:
        db.row_factory = sqlite3.Row
        result["new_requests"] = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM request_history WHERE request_id > ? ORDER BY request_id",
                (PRIOR_REQUEST_ID,),
            )
        ]
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["validate", "run"])
    parser.add_argument(
        "--case", action="append", help="Select one or more case IDs; default is all."
    )
    args = parser.parse_args()
    if missing := set(args.case or ()) - CASES_BY_ID.keys():
        parser.error(f"Unknown cases: {sorted(missing)}")
    model = Foundry.from_env() if args.mode != "validate" else None
    failures = 0
    for case in CASES:
        if args.case and case.id not in args.case:
            continue
        with TemporaryDirectory() as folder:
            services = prepare(case, Path(folder) / "equipment.sqlite3")
            validate(case, services)
            if model:
                result = await capture(case, services, model.respond)
                failures += int("error" in result)
                print(json.dumps(result), flush=True)
            else:
                print(f"{case.id}: validated")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
