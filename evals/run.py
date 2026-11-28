"""Run and grade the equipment agent or validate its evaluation fixtures offline."""

import argparse
import asyncio
import json
import sqlite3
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TextIO, get_args

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
from .checks import Run
from .judge import grade
from .models import EvalCase

PRIOR_REQUEST_ID = 42
RESULTS = Path(__file__).resolve().parent / "results"


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


async def run_cases(
    cases: list[EvalCase],
    output: TextIO,
    agent: Foundry | None,
    judge: Foundry | None = None,
) -> int:
    failures = 0
    for case in cases:
        with TemporaryDirectory() as folder:
            services = prepare(case, Path(folder) / "equipment.sqlite3")
            validate(case, services)
            if agent is None:
                print(f"{case.id}: validated", file=output)
                continue
            result = await capture(case, services, agent.respond)
        if judge is None:
            failures += int("error" in result)
        else:
            score = await grade(
                case, Run.model_validate(result), judge.respond, judge.model
            )
            result["grade"] = score.model_dump(mode="json")
            failures += int(not score.passed)
        print(json.dumps(result), file=output, flush=True)
    return failures


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["run", "validate", "capture"])
    parser.add_argument(
        "--case", action="append", help="Select one or more case IDs; default is all."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="New JSONL file for run mode (default: timestamped file in evals/results).",
    )
    parser.add_argument(
        "--judge-model",
        help="Foundry judge deployment for run mode (default: FOUNDRY_MODEL).",
    )
    args = parser.parse_args()
    if args.mode != "run" and (args.output is not None or args.judge_model is not None):
        parser.error("--output and --judge-model require run mode.")
    selected = set(args.case or ())
    if missing := selected - CASES_BY_ID.keys():
        parser.error(f"Unknown cases: {sorted(missing)}")
    cases = [case for case in CASES if not selected or case.id in selected]
    try:
        agent = Foundry.from_env() if args.mode != "validate" else None
    except ValueError as error:
        parser.error(str(error))
    if args.mode == "run":
        assert agent is not None
        judge = replace(agent, model=args.judge_model) if args.judge_model else agent
        path = (
            args.output
            or RESULTS / f"run-{datetime.now(UTC):%Y-%m-%d_%H%M%S_%fZ}.jsonl"
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as output:
                print(f"Saving results to {path}", file=sys.stderr)
                failures = await run_cases(cases, output, agent, judge)
        except OSError as error:
            parser.exit(2, f"{error}\n")
        print(f"{len(cases) - failures}/{len(cases)} cases passed.", file=sys.stderr)
    else:
        failures = await run_cases(cases, sys.stdout, agent)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
