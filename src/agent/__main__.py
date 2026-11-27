"""Handle one equipment request through Foundry and a running MCP server."""

import argparse
import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .client import bind_call, discover
from .foundry import AgentError, Foundry
from .loop import Respond, run_agent_loop


async def run(url: str, employee_id: str, request: str, respond: Respond) -> str:
    async with (
        streamable_http_client(url) as (reader, writer, _),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        tools = await discover(session)
        return await run_agent_loop(
            employee_id, request, respond, tools, bind_call(session)
        )


def describe_failure(error: Exception) -> str:
    if isinstance(error, ExceptionGroup):
        return "\n".join(describe_failure(cause) for cause in error.exceptions)
    if isinstance(error, httpx.ConnectError):
        return (
            "Could not connect to the equipment MCP server. "
            "Check --url or start the local server in another terminal with "
            "uv run --locked python -m server --database equipment.sqlite3"
        )
    return str(error) or type(error).__name__


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("employee_id")
    parser.add_argument("request")
    parser.add_argument("--url", default="http://127.0.0.1:43817/mcp")
    args = parser.parse_args()
    try:
        model = Foundry.from_env()
        answer = asyncio.run(
            run(args.url, args.employee_id, args.request, model.respond)
        )
    except (ValueError, AgentError, httpx.HTTPError, ExceptionGroup) as error:
        parser.exit(1, f"Agent failed: {describe_failure(error)}\n")
    print(f"Final: {answer}")


if __name__ == "__main__":
    main()
