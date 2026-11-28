import asyncio
import sqlite3
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def call_tool(
    session: ClientSession, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    result = await session.call_tool(name, arguments)
    if result.isError or result.structuredContent is None:
        pytest.fail(f"{name} failed to return structured content: {result.content}")
    print(f"{name} -> {result.structuredContent}")
    return result.structuredContent


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_missing_laptop_issue_date_opens_review(
    equipment_url: str, tmp_path: Path
) -> None:
    employee_id = "M2"
    request = "Can I get a replacement for my laptop?"
    required_tools = {
        "get_employee_info",
        "get_policy_limits",
        "check_request_eligibility",
        "flag_for_human_review",
    }

    async with (
        asyncio.timeout(15),
        streamable_http_client(equipment_url) as (reader, writer, _),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()

        names = {tool.name for tool in (await session.list_tools()).tools}
        employee = await call_tool(
            session, "get_employee_info", {"employee_id": employee_id}
        )
        role = employee["role"]
        policy = await call_tool(session, "get_policy_limits", {"role": role})
        eligibility = await call_tool(
            session,
            "check_request_eligibility",
            {"employee_id": employee_id, "item": "laptop"},
        )
        reason = eligibility["reason"]
        review = await call_tool(
            session,
            "flag_for_human_review",
            {"employee_id": employee_id, "request": request, "reason": reason},
        )

    with sqlite3.connect(tmp_path / "equipment.sqlite3") as db:
        reviews = db.execute(
            "SELECT id, employee_id, request, reason FROM human_review"
        ).fetchall()
    assert {
        "required_tools": required_tools & names,
        "employee_id": employee["employee_id"],
        "role": role,
        "current_equipment": employee["current_equipment"],
        "policy": policy,
        "eligibility": (
            eligibility["decision"],
            reason,
            eligibility["next_eligible_date"],
        ),
        "review": review,
        "stored_reviews": reviews,
    } == {
        "required_tools": required_tools,
        "employee_id": employee_id,
        "role": "Manager",
        "current_equipment": [{"item": "laptop", "issued": None}],
        "policy": {"laptop": 2, "monitor": 3},
        "eligibility": ("human_review", "Missing laptop issue date", None),
        "review": {"result": "R1"},
        "stored_reviews": [(1, employee_id, request, "Missing laptop issue date")],
    }
