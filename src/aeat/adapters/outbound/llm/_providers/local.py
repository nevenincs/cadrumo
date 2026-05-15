"""Local provider adapter for Ollama-compatible runtimes.

Speaks the Ollama ``/api/chat`` endpoint exposed at
:data:`_OLLAMA_API_URL` and adapts its response into the
:class:`aeat.adapters.outbound.llm._providers.base.ProviderCompletion` shape.
The adapter assumes the runtime is reachable on localhost; remote Ollama
deployments are out of scope.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .....core.config import Settings
from .._errors import LLMProviderError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, raise_rate_limit

_OLLAMA_API_URL = Settings.external_constants().online_services.llm_endpoints.ollama_chat
"""Ollama ``/api/chat`` endpoint targeted by :class:`LocalAdapter`."""


class _LocalMessage(BaseModel):
    """Single message returned in an Ollama chat response."""

    model_config = ConfigDict(strict=True, frozen=True)

    content: str


class _LocalResponse(BaseModel):
    """Top-level Ollama chat response envelope.

    Attributes:
        model: Model identifier reported by the runtime.
        message: Generated message payload.
        prompt_eval_count: Tokens evaluated for the prompt.
        eval_count: Tokens evaluated for the generated output.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    model: str
    message: _LocalMessage
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


class LocalAdapter(_ProviderAdapter):
    """Provider adapter that invokes a local Ollama-compatible HTTP endpoint."""

    provider = LLMProvider.LOCAL

    def __init__(self, timeout_s: int) -> None:
        """Initialize the adapter.

        Args:
            timeout_s: Per-request HTTP timeout in seconds.
        """
        self._timeout_s = timeout_s

    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a chat completion request against the local endpoint.

        Args:
            request: Normalized provider request.

        Returns:
            Normalized completion containing the trimmed assistant message
            and reported token counts.

        Raises:
            :exc:`aeat.adapters.outbound.llm.LLMRateLimitError`: When the
                runtime returns HTTP 429.
            :exc:`aeat.adapters.outbound.llm.LLMProviderError`: When the
                runtime returns any other HTTP error status.
        """

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
