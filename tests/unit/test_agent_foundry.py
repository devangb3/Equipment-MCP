import json

import httpx
import pytest

from agent.foundry import AgentError, Foundry, Item, message_text


def test_foundry_rejects_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_BASE_URL", "https://resource.example")
    monkeypatch.setenv("FOUNDRY_MODEL", "deployment")
    monkeypatch.delenv("FOUNDRY_API_KEY", raising=False)

    with pytest.raises(ValueError, match="FOUNDRY_API_KEY"):
        Foundry.from_env()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("cache_key", [None, "equipment-agent-v1"])
async def test_foundry_replays_stateless_tool_history(
    monkeypatch: pytest.MonkeyPatch,
    cache_key: str | None,
) -> None:
    endpoint = "https://resource.example/openai/v1/responses"
    history: list[Item] = [
        {"role": "user", "content": "I need a monitor."},
        {
            "type": "function_call",
            "call_id": "c1",
            "name": "get_employee_info",
            "arguments": '{"employee_id":"S1"}',
        },
        {
            "type": "function_call_output",
            "call_id": "c1",
            "output": '{"role":"Standard employee"}',
        },
    ]
    requests: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Draft"}],
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    monkeypatch.setenv("FOUNDRY_BASE_URL", "https://resource.example")
    monkeypatch.setenv("FOUNDRY_API_KEY", "fixture-key")
    monkeypatch.setenv("FOUNDRY_MODEL", "deployment")
    monkeypatch.setenv("FOUNDRY_PROMPT_CACHE_KEY", cache_key or "")
    model = Foundry.from_env()

    output = await model.respond("Investigate", history, [])

    (sent,) = requests
    assert (
        sent.method,
        str(sent.url),
        sent.headers["api-key"],
        json.loads(sent.content),
        message_text(output),
    ) == (
        "POST",
        endpoint,
        "fixture-key",
        {
            **({"prompt_cache_key": cache_key} if cache_key else {}),
            "model": "deployment",
            "instructions": "Investigate",
            "input": history,
            "tools": [],
            "parallel_tool_calls": False,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        },
        "Draft",
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://resource.example",
        "https://user:secret@resource.example",
        "https://resource.example?x=1",
        "https://resource.example#fragment",
        "https://resource.example/other",
        "https:///openai/v1",
    ],
)
def test_foundry_rejects_a_base_url_that_is_not_the_resource_endpoint(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("FOUNDRY_BASE_URL", url)
    monkeypatch.setenv("FOUNDRY_MODEL", "deployment")
    monkeypatch.setenv("FOUNDRY_API_KEY", "fixture-key")

    with pytest.raises(ValueError, match="FOUNDRY_BASE_URL"):
        Foundry.from_env()


def configured(monkeypatch: pytest.MonkeyPatch, reply: httpx.MockTransport) -> Foundry:
    client = httpx.AsyncClient(transport=reply)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    monkeypatch.setenv("FOUNDRY_BASE_URL", "https://resource.example")
    monkeypatch.setenv("FOUNDRY_MODEL", "deployment")
    monkeypatch.setenv("FOUNDRY_API_KEY", "fixture-key")
    monkeypatch.setenv("FOUNDRY_PROMPT_CACHE_KEY", "")
    return Foundry.from_env()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_foundry_reports_an_unreachable_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    model = configured(monkeypatch, httpx.MockTransport(refuse))

    with pytest.raises(AgentError, match="Could not connect to the configured Foundry"):
        await model.respond("Investigate", [], [])


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_foundry_rejects_an_incomplete_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def incomplete(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "incomplete", "output": []})

    model = configured(monkeypatch, httpx.MockTransport(incomplete))

    with pytest.raises(AgentError, match="Foundry response status was incomplete"):
        await model.respond("Investigate", [], [])


@pytest.mark.parametrize(
    "output",
    [
        [],
        [{"type": "reasoning"}],
        [{"type": "message", "content": [{"type": "output_text", "text": "  "}]}],
    ],
)
def test_message_text_rejects_output_without_response_text(output: list[Item]) -> None:
    with pytest.raises(AgentError, match="Foundry returned no response text"):
        message_text(output)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize(
    "body",
    [
        "not-json",
        '{"status":"completed","output":null}',
        '{"status":"completed","output":[]}',
    ],
)
async def test_foundry_rejects_invalid_or_empty_envelopes(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    model = configured(
        monkeypatch, httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    )

    with pytest.raises(AgentError, match="Foundry returned"):
        await model.respond("Investigate", [], [])
