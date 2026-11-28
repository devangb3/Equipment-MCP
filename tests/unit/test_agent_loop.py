import asyncio
import json

import pytest

from agent.foundry import AgentError, Item
from agent.loop import run_agent_loop

TOOLS: list[Item] = [{"name": "get_employee_info"}]


def function_call(name: str, arguments: str, call_id: str = "c1") -> Item:
    return {
        "type": "function_call",
        "name": name,
        "call_id": call_id,
        "arguments": arguments,
    }


async def unused_tool(name: str, arguments: Item) -> Item:
    raise AssertionError(f"{name} should not be called")


@pytest.mark.parametrize(
    ("employee_id", "request_text"),
    [(" ", "I need a monitor."), ("S1", " ")],
)
def test_blank_employee_or_request_is_rejected(
    employee_id: str, request_text: str
) -> None:
    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        raise AssertionError("model should not be called")

    with pytest.raises(ValueError, match="Supply an employee ID and a request"):
        asyncio.run(
            run_agent_loop(
                employee_id, request_text, respond, TOOLS, unused_tool, lambda _: None
            )
        )


def test_two_tool_calls_in_one_turn_are_rejected() -> None:
    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        return [
            function_call("get_employee_info", '{"purpose": "Look up the employee"}'),
            function_call(
                "get_employee_info", '{"purpose": "Look up the employee again"}', "c2"
            ),
        ]

    with pytest.raises(AgentError, match="Expected one tool call per turn"):
        asyncio.run(
            run_agent_loop(
                "S1", "I need a monitor.", respond, TOOLS, unused_tool, lambda _: None
            )
        )


def test_unavailable_tool_is_rejected() -> None:
    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        return [function_call("submit_request", '{"purpose": "File the request"}')]

    with pytest.raises(AgentError, match="Unavailable tool: submit_request"):
        asyncio.run(
            run_agent_loop(
                "S1", "I need a monitor.", respond, TOOLS, unused_tool, lambda _: None
            )
        )


@pytest.mark.parametrize(
    "arguments",
    ["[]", "null", '{"employee_id": "S1"}', '{"purpose": 1}'],
)
def test_tool_call_without_a_public_purpose_is_rejected(arguments: str) -> None:
    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        return [function_call("get_employee_info", arguments)]

    with pytest.raises(AgentError, match="public purpose"):
        asyncio.run(
            run_agent_loop(
                "S1", "I need a monitor.", respond, TOOLS, unused_tool, lambda _: None
            )
        )


def test_turn_limit_stops_an_open_investigation() -> None:
    calls = 0

    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        return [
            function_call(
                "get_employee_info",
                json.dumps({"purpose": "Look up the employee", "employee_id": "S1"}),
            )
        ]

    async def lookup(name: str, arguments: Item) -> Item:
        nonlocal calls
        calls += 1
        return {"role": "Standard employee"}

    try:
        asyncio.run(
            run_agent_loop(
                "S1", "I need a monitor.", respond, TOOLS, lookup, lambda _: None
            )
        )
        outcome = None
    except AgentError as error:
        outcome = (str(error), calls)

    assert outcome == ("Agent reached its turn limit before producing a draft.", 10)


@pytest.mark.parametrize(
    "arguments",
    [
        "{broken",
        '{"purpose":"check","item":NaN}',
        '{"purpose":"check","item":"monitor","item":"laptop"}',
    ],
)
def test_malformed_arguments_fail_closed(arguments: str) -> None:
    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        return [function_call("get_employee_info", arguments)]

    with pytest.raises(AgentError, match="Invalid tool arguments"):
        asyncio.run(
            run_agent_loop("S1", "monitor", respond, TOOLS, unused_tool, lambda _: None)
        )


@pytest.mark.parametrize(
    "field,value", [("name", ""), ("call_id", " "), ("arguments", 7), ("call_id", None)]
)
def test_invalid_action_envelope_is_rejected(field: str, value: object) -> None:
    async def respond(
        instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        action = function_call("get_employee_info", '{"purpose":"check"}')
        action[field] = value
        return [action]

    with pytest.raises(AgentError, match="Invalid tool call"):
        asyncio.run(
            run_agent_loop("S1", "monitor", respond, TOOLS, unused_tool, lambda _: None)
        )
