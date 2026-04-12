"""OpenAI provider adapter."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, Field

from aeat.llm._errors import LLMConfigError, LLMProviderError
from aeat.llm._models import LLMProvider
from aeat.llm._providers.base import ProviderCompletion, ProviderRequest, _ProviderAdapter, raise_rate_limit


class _OpenAIUsage(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class _OpenAIMessage(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    content: str | None = None


class _OpenAIChoice(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    message: _OpenAIMessage


class _OpenAIResponse(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    model: str
    choices: tuple[_OpenAIChoice, ...]
    usage: _OpenAIUsage


class OpenAIAdapter(_ProviderAdapter):
    """Execute requests against OpenAI Chat Completions."""

    provider = LLMProvider.OPENAI

    def __init__(self, api_key: str, timeout_s: int) -> None:
        if not api_key:
            msg = "AEAT_LLM_OPENAI_API_KEY must be set for the OpenAI provider."
            raise LLMConfigError(msg)
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request."""

        messages: list[dict[str, str]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": request.model,
                    "messages": messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            )
        if response.status_code == 429:
            raise_rate_limit("OpenAI rate limit exceeded.", response.headers.get("retry-after"))
        if response.status_code >= 400:
            raise LLMProviderError(f"OpenAI API failure ({response.status_code}).")
        parsed = _OpenAIResponse.model_validate_json(response.text)
        text = parsed.choices[0].message.content or ""
        return ProviderCompletion(
            text=text.strip(),
            model=parsed.model,
            input_tokens=parsed.usage.prompt_tokens,
            output_tokens=parsed.usage.completion_tokens,
            provider_request_id=parsed.id,
        )
