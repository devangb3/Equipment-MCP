import asyncio
from typing import cast

import pytest
from mcp import ClientSession
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from agent.client import discover, execute_tool
from agent.foundry import AgentError, Item


def tool(name: str, *required: str) -> Tool:
    return Tool(
        name=name,
        description=name,
        inputSchema={
            "type": "object",
            "properties": {field: {"type": "string"} for field in required},
            "required": list(required),
        },
    )


class ToolSession:
    def __init__(
        self, pages: list[ListToolsResult], result: CallToolResult | None = None
    ) -> None:
        self.pages = pages
        self.result = result
        self.cursors: list[str | None] = []

    async def list_tools(self, params: PaginatedRequestParams) -> ListToolsResult:
        self.cursors.append(params.cursor)
        return self.pages.pop(0)

    async def call_tool(self, name: str, arguments: Item) -> CallToolResult:
        if self.result is None:
            raise AssertionError("tool result was not arranged")
        return self.result


def test_discover_follows_the_cursor_and_requires_purpose_for_every_tool() -> None:
    session = ToolSession(
        [
            ListToolsResult(
                tools=[
                    tool("get_employee_info", "employee_id"),
                    tool("submit_request", "employee_id", "item", "request"),
                ],
                nextCursor="more",
            ),
            ListToolsResult(
                tools=[
                    tool("get_policy_limits", "role"),
                    tool("check_request_eligibility", "employee_id", "item"),
                    tool("flag_for_human_review", "employee_id", "request", "reason"),
                ]
            ),
        ]
    )

    definitions = asyncio.run(discover(cast(ClientSession, session)))

    observed = []
    for definition in definitions:
        parameters = cast(Item, definition["parameters"])
        properties = cast(dict[str, Item], parameters["properties"])
        observed.append(
            (definition["name"], parameters["required"], properties["purpose"]["type"])
        )

    assert (observed, session.cursors) == (
        [
            ("get_employee_info", ["employee_id", "purpose"], "string"),
            ("get_policy_limits", ["role", "purpose"], "string"),
            ("check_request_eligibility", ["employee_id", "item", "purpose"], "string"),
            (
                "flag_for_human_review",
                ["employee_id", "request", "reason", "purpose"],
                "string",
            ),
        ],
        [None, "more"],
    )


def test_discover_rejects_a_server_missing_required_tools() -> None:
    session = ToolSession(
        [ListToolsResult(tools=[tool("get_employee_info", "employee_id")])]
    )

    with pytest.raises(AgentError, match="missing required tools"):
        asyncio.run(discover(cast(ClientSession, session)))


def test_failed_review_is_not_treated_as_an_observation() -> None:
    session = ToolSession(
        [],
        CallToolResult(
            content=[TextContent(type="text", text="database locked")],
            isError=True,
        ),
    )

    with pytest.raises(AgentError, match="Review was not confirmed: database locked"):
        asyncio.run(
            execute_tool(
                cast(ClientSession, session),
                "flag_for_human_review",
                {"employee_id": "M1"},
            )
        )


def test_tool_without_structured_content_is_rejected() -> None:
    session = ToolSession(
        [],
        CallToolResult(content=[TextContent(type="text", text="ok")], isError=False),
    )

    with pytest.raises(
        AgentError, match="get_employee_info returned no structured result"
    ):
        asyncio.run(execute_tool(cast(ClientSession, session), "get_employee_info", {}))


def test_discovery_rejects_cyclic_pagination() -> None:
    session = ToolSession(
        [
            ListToolsResult(tools=[], nextCursor="same"),
            ListToolsResult(tools=[], nextCursor="same"),
        ]
    )

    with pytest.raises(AgentError, match="pagination"):
        asyncio.run(discover(cast(ClientSession, session)))


def test_discovery_rejects_duplicate_tool_names() -> None:
    session = ToolSession(
        [ListToolsResult(tools=[tool("get_employee_info"), tool("get_employee_info")])]
    )

    with pytest.raises(AgentError, match="Duplicate tool"):
        asyncio.run(discover(cast(ClientSession, session)))
