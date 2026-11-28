"""Adapt the equipment MCP session to the model's function-call interface."""

from functools import partial

from mcp import ClientSession
from mcp.types import PaginatedRequestParams, TextContent

from .foundry import AgentError, Item
from .loop import CallTool

TOOLS = {
    "get_employee_info",
    "get_policy_limits",
    "check_request_eligibility",
    "flag_for_human_review",
}


async def discover(session: ClientSession) -> list[Item]:
    definitions: list[Item] = []
    cursor = None
    seen_cursors: set[str] = set()
    seen_tools: set[str] = set()
    for _ in range(100):
        page = await session.list_tools(params=PaginatedRequestParams(cursor=cursor))
        for tool in page.tools:
            if tool.name not in TOOLS:
                continue
            if tool.name in seen_tools:
                raise AgentError(f"Duplicate tool definition: {tool.name}")
            seen_tools.add(tool.name)
            schema = tool.inputSchema
            properties = {
                **schema["properties"],
                "purpose": {
                    "type": "string",
                    "description": "Brief public description of what this action checks.",
                },
            }
            parameters = {
                **schema,
                "properties": properties,
                "required": [*schema.get("required", []), "purpose"],
            }
            definitions.append(
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                    "strict": False,
                }
            )
        cursor = page.nextCursor
        if not cursor:
            break
        if cursor in seen_cursors:
            raise AgentError("Equipment MCP pagination repeated a cursor.")
        seen_cursors.add(cursor)
    else:
        raise AgentError("Equipment MCP pagination exceeded 100 pages.")
    if {d["name"] for d in definitions} != TOOLS:
        raise AgentError("Equipment MCP server is missing required tools.")
    return definitions


def bind_call(session: ClientSession) -> CallTool:
    return partial(execute_tool, session)


async def execute_tool(session: ClientSession, name: str, arguments: Item) -> Item:
    result = await session.call_tool(name, arguments)
    if result.isError:
        detail = " ".join(
            block.text for block in result.content if isinstance(block, TextContent)
        )
        if name == "flag_for_human_review":
            raise AgentError(f"Review was not confirmed: {detail}")
        return {"error": detail}
    if result.structuredContent is None:
        raise AgentError(f"{name} returned no structured result.")
    return result.structuredContent
