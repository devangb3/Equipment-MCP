import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from agent.foundry import AgentError, Foundry, Item, ProviderUnavailable
from agent.providers import Failover, OpenRouter, configured_model, portable_history

OUTPUT: list[Item] = [
    {"type": "message", "content": [{"type": "output_text", "text": "ok"}]}
]


def status_error(status: int) -> httpx.HTTPStatusError:
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://provider.example")
    )
    return httpx.HTTPStatusError(
        "provider error", request=response.request, response=response
    )


@pytest.mark.parametrize(
    "error",
    [
        status_error(408),
        status_error(429),
        status_error(500),
        status_error(503),
        httpx.ReadTimeout("timeout"),
        httpx.ConnectError("refused"),
        httpx.RemoteProtocolError("reset"),
        ProviderUnavailable("unreachable"),
    ],
)
def test_failover_is_sticky_and_preserves_observations(error: Exception) -> None:
    primary = AsyncMock(side_effect=error)
    backup = AsyncMock(return_value=OUTPUT)
    router = Failover(primary, backup)
    history: list[Item] = [
        {"type": "function_call_output", "call_id": "c1", "output": '{"result":"R1"}'}
    ]

    async def exercise() -> list[list[Item]]:
        return [
            await router.respond("check", history, []),
            await router.respond("reflect", [], []),
        ]

    answers = asyncio.run(exercise())

    assert (
        answers,
        primary.await_count,
        backup.await_args_list[0].args,
        backup.await_count,
    ) == ([OUTPUT, OUTPUT], 1, ("check", history, []), 2)


@pytest.mark.parametrize(
    "error",
    [
        status_error(400),
        status_error(401),
        status_error(403),
        status_error(404),
        status_error(422),
        AgentError("incomplete"),
        ValueError("bad config"),
    ],
)
def test_permanent_errors_do_not_trigger_fallback(error: Exception) -> None:
    fallback = AsyncMock(side_effect=AssertionError("must not call fallback"))
    router = Failover(AsyncMock(side_effect=error), fallback)

    with pytest.raises(type(error), match=str(error)):
        asyncio.run(router.respond("check", [], []))


def test_exhausted_fallback_does_not_leak_provider_details() -> None:
    router = Failover(
        AsyncMock(side_effect=httpx.ReadTimeout("secret-primary")),
        AsyncMock(side_effect=httpx.ReadTimeout("secret-fallback")),
    )

    with pytest.raises(
        AgentError, match=r"^Configured fallback model is unavailable\.$"
    ):
        asyncio.run(router.respond("check", [], []))


def test_cancellation_does_not_trigger_fallback() -> None:
    router = Failover(
        AsyncMock(side_effect=asyncio.CancelledError),
        AsyncMock(side_effect=AssertionError("must not call")),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(router.respond("check", [], []))


def test_portable_history_removes_private_reasoning_and_ids() -> None:
    history: list[Item] = [
        {"role": "user", "content": "monitor"},
        {"type": "reasoning", "encrypted_content": "private-ciphertext"},
        {
            "type": "message",
            "id": "private-message",
            "role": "assistant",
            "content": [
                {"type": "output_text", "text": "checking", "annotations": ["private"]}
            ],
        },
        {
            "type": "function_call",
            "id": "private-call",
            "call_id": "c1",
            "name": "get_employee_info",
            "arguments": "{}",
        },
        {
            "type": "function_call_output",
            "call_id": "c1",
            "output": '{"role":"Manager"}',
        },
    ]

    result = portable_history(history)

    assert result == [
        history[0],
        {"role": "assistant", "content": "checking"},
        {
            "type": "function_call",
            "call_id": "c1",
            "name": "get_employee_info",
            "arguments": "{}",
        },
        history[4],
    ]


def test_portable_history_rejects_unknown_items() -> None:
    with pytest.raises(AgentError, match="Unsupported item"):
        portable_history([{"type": "computer_call"}])


def test_openrouter_uses_responses_protocol_and_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "completed", "output": OUTPUT})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(reply), **kwargs
        ),
    )
    model = OpenRouter("vendor/tool-model", "test-key")
    tools: list[Item] = [
        {"type": "function", "name": "lookup", "parameters": {"type": "object"}}
    ]

    result = asyncio.run(
        model.respond("Investigate", [{"role": "user", "content": "monitor"}], tools)
    )

    (request,) = requests
    assert (
        str(request.url),
        request.headers["Authorization"],
        "api-key" in request.headers,
        json.loads(request.content),
        result,
    ) == (
        "https://openrouter.ai/api/v1/responses",
        "Bearer test-key",
        False,
        {
            "model": "vendor/tool-model",
            "instructions": "Investigate",
            "input": [{"role": "user", "content": "monitor"}],
            "tools": tools,
            "parallel_tool_calls": False,
            "store": False,
        },
        OUTPUT,
    )


@pytest.mark.parametrize(
    "body",
    [
        "not-json",
        '{"status":"completed","output":null}',
        '{"status":"completed","output":[]}',
        '{"status":"incomplete","output":[]}',
    ],
)
def test_openrouter_fails_closed_on_invalid_response(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)),
            **kwargs,
        ),
    )

    with pytest.raises(AgentError):
        asyncio.run(OpenRouter("vendor/model", "key").respond("check", [], []))


@pytest.mark.parametrize("missing", ["OPENROUTER_API_KEY", "OPENROUTER_MODEL"])
def test_openrouter_requires_explicit_credentials_and_model(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    monkeypatch.delenv(missing)

    with pytest.raises(ValueError, match=missing):
        OpenRouter.from_env()


@pytest.mark.parametrize(
    "provider,fallback,expected",
    [
        ("foundry", "", Foundry),
        ("foundry", "openrouter", Failover),
        ("openrouter", "", OpenRouter),
    ],
)
def test_provider_configuration(
    monkeypatch: pytest.MonkeyPatch, provider: str, fallback: str, expected: type
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", provider)
    monkeypatch.setenv("MODEL_FALLBACK_PROVIDER", fallback)
    monkeypatch.setenv("FOUNDRY_BASE_URL", "https://foundry.example")
    monkeypatch.setenv("FOUNDRY_API_KEY", "key")
    monkeypatch.setenv("FOUNDRY_MODEL", "deployment")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")

    model = configured_model()

    assert isinstance(model, expected)


@pytest.mark.parametrize(
    "provider,fallback",
    [("unknown", ""), ("foundry", "unknown"), ("openrouter", "openrouter")],
)
def test_invalid_routing_configuration(
    monkeypatch: pytest.MonkeyPatch, provider: str, fallback: str
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", provider)
    monkeypatch.setenv("MODEL_FALLBACK_PROVIDER", fallback)

    with pytest.raises(ValueError, match="MODEL_"):
        configured_model()


def test_credentials_are_not_in_repr() -> None:
    assert "private-api-key" not in repr(OpenRouter("vendor/model", "private-api-key"))


def test_fallback_authentication_error_is_not_retried() -> None:
    router = Failover(
        AsyncMock(side_effect=httpx.ReadTimeout("primary timeout")),
        AsyncMock(side_effect=status_error(401)),
    )

    with pytest.raises(httpx.HTTPStatusError, match="provider error"):
        asyncio.run(router.respond("check", [], []))
