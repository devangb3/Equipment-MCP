"""Opt-in OpenRouter routing and bounded, per-request provider failover."""

import logging
import os
from dataclasses import dataclass, field

import httpx
from pydantic import ValidationError

from .foundry import AgentError, Foundry, Item, ProviderUnavailable, Response
from .refinement import Respond

logger = logging.getLogger(__name__)


def portable_history(history: list[Item]) -> list[Item]:
    """Keep public messages and tool observations; omit provider-private reasoning/IDs."""
    result: list[Item] = []
    for item in history:
        kind = item.get("type")
        if kind == "reasoning":
            continue
        if kind == "function_call":
            fields = ("type", "call_id", "name", "arguments")
        elif kind == "function_call_output":
            fields = ("type", "call_id", "output")
        elif kind == "message" or (kind is None and "role" in item):
            fields = ("role", "content")
            content = item.get("content")
            if isinstance(content, list):
                # Responses messages contain text blocks with provider-specific metadata.
                parts = [
                    part["text"]
                    for part in content
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                ]
                result.append(
                    {"role": item.get("role", "assistant"), "content": "\n".join(parts)}
                )
                continue
        else:
            raise AgentError("Unsupported item in model conversation history.")
        result.append({key: item[key] for key in fields if key in item})
    return result


@dataclass(frozen=True)
class OpenRouter:
    model: str
    key: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "OpenRouter":
        def setting(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise ValueError(f"Set {name} in .env using .env.example.")
            return value

        return cls(setting("OPENROUTER_MODEL"), setting("OPENROUTER_API_KEY"))

    async def respond(
        self, instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        body = {
            "model": self.model,
            "instructions": instructions,
            "input": portable_history(history),
            "tools": tools,
            "parallel_tool_calls": False,
            "store": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/responses",
                json=body,
                headers={"Authorization": f"Bearer {self.key}"},
            )
            response.raise_for_status()
        try:
            result = Response.model_validate_json(response.content)
        except ValidationError:
            raise AgentError(
                "OpenRouter returned an invalid response envelope."
            ) from None
        if result.status != "completed" or not result.output:
            raise AgentError(
                "OpenRouter did not return a completed, nonempty response."
            )
        return result.output


def transient(error: Exception) -> bool:
    """Fail over on transport failures, throttling, request timeout, and server errors."""
    if isinstance(error, (httpx.TransportError, ProviderUnavailable)):
        return True
    return isinstance(error, httpx.HTTPStatusError) and (
        error.response.status_code in (408, 429)
        or 500 <= error.response.status_code < 600
    )


@dataclass
class Failover:
    """Switch once per agent request; never retry an MCP action or restart its loop."""

    primary: Respond
    fallback: Respond
    using_fallback: bool = field(default=False, init=False)

    async def respond(
        self, instructions: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        if not self.using_fallback:
            try:
                return await self.primary(instructions, history, tools)
            except (httpx.HTTPError, AgentError) as error:
                if not transient(error):
                    raise
                self.using_fallback = True
                logger.warning(
                    "Primary model unavailable; switching to configured OpenRouter fallback."
                )
        try:
            return await self.fallback(instructions, history, tools)
        except (httpx.HTTPError, AgentError) as error:
            if not transient(error):
                raise
            raise AgentError("Configured fallback model is unavailable.") from None


def configured_model() -> Foundry | OpenRouter | Failover:
    """Default to Foundry; external fallback requires an explicit configuration choice."""
    provider = os.getenv("MODEL_PROVIDER", "foundry").strip().casefold()
    fallback = os.getenv("MODEL_FALLBACK_PROVIDER", "").strip().casefold()
    if provider not in ("foundry", "openrouter"):
        raise ValueError("MODEL_PROVIDER must be foundry or openrouter.")
    if fallback not in ("", "openrouter") or (provider == "openrouter" and fallback):
        raise ValueError(
            "MODEL_FALLBACK_PROVIDER may only be openrouter with Foundry primary."
        )
    if provider == "openrouter":
        return OpenRouter.from_env()
    primary = Foundry.from_env()
    if fallback:
        return Failover(primary.respond, OpenRouter.from_env().respond)
    return primary
