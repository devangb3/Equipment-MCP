"""Connect to the equipment server and call get_employee_info."""

import argparse
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent


class EmployeeLookupError(Exception):
    """The equipment server did not return an employee record."""


async def lookup(session: ClientSession, employee_id: str) -> CallToolResult:
    """Initialize, list tools, and call get_employee_info for one employee."""
    info = await session.initialize()
    names = [tool.name for tool in (await session.list_tools()).tools]
    print(f"Connected to {info.serverInfo.name}. Registered tools: {names}")
    return await session.call_tool("get_employee_info", {"employee_id": employee_id})


def employee_record(employee_id: str, result: CallToolResult) -> dict[str, object]:
    """Return the employee record, or raise if the server reported an error."""
    if result.isError or result.structuredContent is None:
        detail = " ".join(
            block.text for block in result.content if isinstance(block, TextContent)
        )
        raise EmployeeLookupError(
            f"get_employee_info({employee_id!r}) failed: {detail}"
        )
    print(f"get_employee_info({employee_id!r}): {result.structuredContent}")
    return result.structuredContent


async def run(url: str, employee_id: str) -> dict[str, object]:
    """Connect to a Streamable HTTP equipment server and look up one employee."""
    async with (
        streamable_http_client(url) as (reader, writer, _),
        ClientSession(reader, writer) as session,
    ):
        result = await lookup(session, employee_id)
    return employee_record(employee_id, result)


def main() -> None:
    """Call get_employee_info on a running equipment server."""
    parser = argparse.ArgumentParser(
        description="Call get_employee_info on the equipment MCP server."
    )
    parser.add_argument(
        "--url", default="http://127.0.0.1:43817/mcp", help="Streamable HTTP endpoint"
    )
    parser.add_argument("--employee-id", default="M1", help="Employee to look up")
    args = parser.parse_args()
    asyncio.run(run(args.url, args.employee_id))


if __name__ == "__main__":
    main()
