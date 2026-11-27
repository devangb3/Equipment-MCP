import json

import httpx
import pytest

from agent.foundry import Foundry, Item, message_text


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
