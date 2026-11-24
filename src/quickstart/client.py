"""Demo client that lists tools on the quickstart server and calls add."""

import argparse
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_ADD_CHECK: tuple[list[str], bool, dict[str, int]] = (["add"], False, {"result": 5})


class QuickstartCheckError(Exception):
    """The quickstart server did not register add and return 2 + 3."""


def integer_content(content: object) -> dict[str, int] | None:
    """Return structured tool content when every value is an int."""
    if content is None:
        return None
    if not isinstance(content, dict):
        raise QuickstartCheckError(f"structured content is {type(content).__name__}, expected an object")
    parsed: dict[str, int] = {}
    for key, value in content.items():
        if not isinstance(key, str) or type(value) is not int:
            raise QuickstartCheckError(f"structured content entry {key!r}: {value!r} is not a string-to-int pair")
        parsed[key] = value
    return parsed


async def check_add(session: ClientSession) -> tuple[list[str], bool, dict[str, int] | None]:
    """Initialize, list tools, and call add(2, 3)."""
    info = await session.initialize()
    names = [tool.name for tool in (await session.list_tools()).tools]
    result = await session.call_tool("add", {"a": 2, "b": 3})
    content = integer_content(result.structuredContent)
    print(f"Connected to {info.serverInfo.name}. Registered tools: {names}. add(2, 3): {content}")
    return (names, result.isError, content)


async def run(url: str) -> tuple[list[str], bool, dict[str, int] | None]:
    """Connect to a Streamable HTTP quickstart server and call add."""
    async with (
        streamable_http_client(url) as (reader, writer, _),
        ClientSession(reader, writer) as session,
    ):
        return await check_add(session)


def main() -> None:
    """Call add on a running quickstart server and require the known result."""
    parser = argparse.ArgumentParser(description="Call add on the quickstart MCP server.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp", help="Streamable HTTP endpoint")
    args = parser.parse_args()
    observed = asyncio.run(run(args.url))
    if observed != EXPECTED_ADD_CHECK:
        raise QuickstartCheckError(f"expected {EXPECTED_ADD_CHECK}, got {observed}")


if __name__ == "__main__":
    main()
