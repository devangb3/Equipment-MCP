"""Stateless Microsoft Foundry Responses API client."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

type Item = dict[str, object]


class AgentError(RuntimeError):
    """The agent could not produce a grounded decision."""


class Response(BaseModel):
    status: str
    output: list[Item]


@dataclass(frozen=True)
class Foundry:
    url: str
    model: str
    key: str = field(repr=False)
    prompt_cache_key: str | None = None

    @classmethod
    def from_env(cls) -> "Foundry":
        def setting(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise ValueError(f"Set {name} in .env using .env.example.")
            return value

        base = urlsplit(setting("FOUNDRY_BASE_URL"))
        if (
            base.scheme != "https"
            or not base.hostname
            or base.username is not None
            or base.query
            or base.fragment
            or base.path.rstrip("/") not in ("", "/openai/v1")
        ):
            raise ValueError(
                "FOUNDRY_BASE_URL must be an HTTPS resource URL with optional /openai/v1."
            )
        return cls(
            f"https://{base.netloc}/openai/v1/responses",
            setting("FOUNDRY_MODEL"),
            setting("FOUNDRY_API_KEY"),
            os.getenv("FOUNDRY_PROMPT_CACHE_KEY", "").strip() or None,
        )

    async def respond(
        self, instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        body = {
            "model": self.model,
            "instructions": instructions,
            "input": history,
            "tools": tools,
            # Each action can depend on the preceding MCP observation.
            "parallel_tool_calls": False,
            "store": False,
            # Replay opaque reasoning items with tool results in stateless mode.
            "include": ["reasoning.encrypted_content"],
        }
        if self.prompt_cache_key:
            body["prompt_cache_key"] = self.prompt_cache_key
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(
                    self.url, json=body, headers={"api-key": self.key}
                )
            except httpx.ConnectError as error:
                raise AgentError(
                    "Could not connect to the configured Foundry endpoint."
                ) from error
            response.raise_for_status()
        result = Response.model_validate_json(response.content)
        if result.status != "completed":
            raise AgentError(f"Foundry response status was {result.status}.")
        return result.output


def message_text(output: list[Item]) -> str:
    parts = [
        part["text"]
        for item in output
        if item.get("type") == "message"
        and isinstance(content := item.get("content"), list)
        for part in content
        if isinstance(part, dict)
        and part.get("type") == "output_text"
        and isinstance(part.get("text"), str)
    ]
    if not (text := "\n".join(parts).strip()):
        raise AgentError("Foundry returned no response text.")
    return text
