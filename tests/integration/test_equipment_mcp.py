import asyncio

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
async def test_missing_laptop_issue_date_opens_review(equipment_url: str) -> None:
    employee_id = "M2"
    request = "Can I get a replacement for my laptop?"
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

    assert {
        "get_employee_info",
        "get_policy_limits",
        "check_request_eligibility",
        "flag_for_human_review",
    } <= names
    assert employee["employee_id"] == employee_id
    assert role == "Manager"
    assert employee["current_equipment"] == [{"item": "laptop", "issued": None}]
    assert policy["laptop"] == 2
    assert eligibility["decision"] == "human_review"
    assert reason == "Missing laptop issue date"
    assert review == {"result": "R1"}
