"""LLM abstraction.

Agents depend on the small `LLMClient` interface, not on OpenAI directly. That keeps them
testable (tests inject a fake) and lets the bot keep working without an API key — the
`OfflineLLM` reports `available = False` and agents fall back to curated content.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient(Protocol):
    available: bool

    async def complete(
        self,
        system: str,
        messages: list[dict],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1800,
        json_mode: bool = False,
    ) -> str: ...


class OfflineLLM:
    available = False

    async def complete(self, system, messages, *, temperature=0.4, max_tokens=1800, json_mode=False) -> str:
        raise LLMError("No LLM configured")


class OpenAILLM:
    available = True

    def __init__(self, api_key: str, model: str, base_url: str | None = None, timeout: float = 60.0):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)
        self._model = model

    async def complete(self, system, messages, *, temperature=0.4, max_tokens=1800, json_mode=False) -> str:
        kwargs: dict = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # network errors, rate limits, auth problems ...
            logger.error("LLM request failed: %s", type(exc).__name__)
            raise LLMError(str(exc)) from exc
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise LLMError("Empty LLM response")
        return content


def parse_json(text: str) -> dict:
    """Parse a JSON object from an LLM reply, tolerating ```json fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("No JSON object in LLM response")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from LLM: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON is not an object")
    return data


def build_llm(api_key: str, model: str, base_url: str | None, timeout: float) -> LLMClient:
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — running with curated offline content only")
        return OfflineLLM()
    return OpenAILLM(api_key, model, base_url, timeout)
