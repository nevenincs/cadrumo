"""Local provider adapter for Ollama-compatible runtimes."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .._errors import LLMProviderError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, raise_rate_limit

_OLLAMA_API_URL = "http://127.0.0.1:11434/api/chat"


class _LocalMessage(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    content: str


class _LocalResponse(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    model: str
    message: _LocalMessage
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


class LocalAdapter(_ProviderAdapter):
    """Execute requests against a local Ollama-compatible endpoint."""

    provider = LLMProvider.LOCAL

    def __init__(self, timeout_s: int) -> None:
        self._timeout_s = timeout_s

    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request."""

        messages: list[dict[str, str]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                _OLLAMA_API_URL,
                json={
                    "model": request.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens,
                    },
                },
            )
        if response.status_code == 429:
            raise_rate_limit("Local Ollama endpoint rate limit exceeded.", response.headers.get("retry-after"))
        if response.status_code >= 400:
            raise LLMProviderError(f"Local Ollama endpoint failure ({response.status_code}).")
        parsed = _LocalResponse.model_validate_json(response.text)
        return ProviderCompletion(
            text=parsed.message.content.strip(),
            model=parsed.model,
            input_tokens=parsed.prompt_eval_count,
            output_tokens=parsed.eval_count,
            provider_request_id=None,
        )
