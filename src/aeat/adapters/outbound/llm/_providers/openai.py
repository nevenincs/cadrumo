"""OpenAI provider adapter for the LLM outbound subpackage.

Speaks the OpenAI ``/v1/chat/completions`` HTTP API and adapts its response
into the :class:`aeat.adapters.outbound.llm._providers.base.ProviderCompletion`
contract.
"""

from __future__ import annotations

from typing import override

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .....core.config import Settings
from .....core.logging import get_logger
from .._errors import LLMConfigError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, check_http_error

_OPENAI_CHAT_URL = Settings().aeat_llm_openai_chat_completions_url

_logger = get_logger(__name__)


class _OpenAIUsage(BaseModel):
    """Token accounting reported by the OpenAI Chat Completions API.

    Attributes:
        prompt_tokens: Tokens charged for the prompt.
        completion_tokens: Tokens charged for the completion.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class _OpenAIMessage(BaseModel):
    """Single assistant message inside a Chat Completions choice."""

    model_config = ConfigDict(strict=True, frozen=True)

    content: str | None = None


class _OpenAIChoice(BaseModel):
    """One choice within an OpenAI Chat Completions response."""

    model_config = ConfigDict(strict=True, frozen=True)

    message: _OpenAIMessage


class _OpenAIResponse(BaseModel):
    """Top-level OpenAI Chat Completions response envelope.

    Attributes:
        id: Vendor-native response identifier (forwarded as
            :attr:`aeat.adapters.outbound.llm._providers.base.ProviderCompletion.provider_request_id`).
        model: Model that served the request.
        choices: Returned chat completion choices.
        usage: Token accounting metadata.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    model: str
    choices: tuple[_OpenAIChoice, ...]
    usage: _OpenAIUsage


class OpenAIAdapter(_ProviderAdapter):
    """Provider adapter that invokes the OpenAI Chat Completions API.

    A non-empty ``api_key`` is mandatory; the adapter refuses to construct
    without one because the underlying API rejects unauthenticated calls.
    """

    provider = LLMProvider.OPENAI

    def __init__(self, api_key: str, timeout_s: int) -> None:
        """Initialize the adapter.

        Args:
            api_key: OpenAI API key.
            timeout_s: Per-request HTTP timeout in seconds.

        Raises:
            LLMConfigError: When ``api_key`` is empty.
        """
        if not api_key:
            msg = "AEAT_LLM_OPENAI_API_KEY must be set for the OpenAI provider."
            raise LLMConfigError(msg)
        self._api_key = api_key
        self._timeout_s = timeout_s

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a Chat Completions request against the OpenAI API.

        Args:
            request: Normalized provider request.

        Returns:
            A :class:`ProviderCompletion` with the first choice's trimmed text and
            reported token counts.

        Raises:
            LLMProviderError: When the API returns a 4xx or 5xx HTTP error status.
        """
        messages: list[dict[str, str]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                _OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": request.model,
                    "messages": messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            )
        check_http_error(response, provider_name="OpenAI", model=request.model, logger=_logger)
        parsed = _OpenAIResponse.model_validate_json(response.text)
        text = parsed.choices[0].message.content or ""
        return ProviderCompletion(
            text=text.strip(),
            model=parsed.model,
            input_tokens=parsed.usage.prompt_tokens,
            output_tokens=parsed.usage.completion_tokens,
            provider_request_id=parsed.id,
        )
