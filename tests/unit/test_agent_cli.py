import httpx
import pytest

from agent.__main__ import describe_failure
from agent.foundry import AgentError


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
