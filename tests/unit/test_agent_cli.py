import sys
from unittest.mock import AsyncMock, call

import httpx
import pytest

from agent.__main__ import describe_failure, main
from agent.foundry import AgentError, Foundry


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        (httpx.ConnectError("Connection refused"), "uv run --locked python -m server"),
        (
            AgentError("Foundry response status was incomplete."),
            "Foundry response status was incomplete.",
        ),
    ],
)
def test_cli_reports_nested_task_group_cause(cause: Exception, expected: str) -> None:
    failure = ExceptionGroup("transport", [ExceptionGroup("session", [cause])])

    message = describe_failure(failure)

    assert expected in message


def test_cli_forwards_request_and_prints_the_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model = Foundry("https://resource.example/openai/v1/responses", "deployment", "key")
    run = AsyncMock(return_value="Approved. First monitor issue.")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agent",
            "S1",
            "I need my first monitor.",
            "--url",
            "http://127.0.0.1:43999/mcp",
        ],
    )
    monkeypatch.setattr(Foundry, "from_env", lambda: model)
    monkeypatch.setattr("agent.__main__.run", run)

    main()

    output = capsys.readouterr()
    assert (
        run.await_args_list,
        output.out,
        output.err,
    ) == (
        [
            call(
                "http://127.0.0.1:43999/mcp",
                "S1",
                "I need my first monitor.",
                model.respond,
            )
        ],
        "Final: Approved. First monitor issue.\n",
        "",
    )


def test_cli_exits_when_the_equipment_server_is_down(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agent", "S1", "I need my first monitor."])
    monkeypatch.setattr(
        Foundry,
        "from_env",
        lambda: Foundry(
            "https://resource.example/openai/v1/responses", "deployment", "key"
        ),
    )

    async def down(url: str, employee_id: str, request: str, respond: object) -> str:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr("agent.__main__.run", down)

    try:
        main()
        outcome = None
    except SystemExit as error:
        outcome = (error.code, capsys.readouterr().err)

    assert outcome == (
        1,
        (
            "Agent failed: Could not connect to the equipment MCP server. "
            "Check --url or start the local server in another terminal with "
            "uv run --locked python -m server --database equipment.sqlite3\n"
        ),
    )


def test_cli_exits_when_foundry_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agent", "S1", "I need my first monitor."])
    monkeypatch.delenv("FOUNDRY_BASE_URL", raising=False)
    monkeypatch.delenv("FOUNDRY_MODEL", raising=False)
    monkeypatch.delenv("FOUNDRY_API_KEY", raising=False)

    try:
        main()
        outcome = None
    except SystemExit as error:
        outcome = (error.code, capsys.readouterr().err)

    assert outcome == (
        1,
        "Agent failed: Set FOUNDRY_BASE_URL in .env using .env.example.\n",
    )
