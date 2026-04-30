"""Anthropic provider adapter."""

from __future__ import annotations

from typing import cast

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from anthropic.types import Message, MessageParam, MetadataParam, TextBlock

from .._errors import LLMConfigError, LLMProviderError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, raise_rate_limit


class AnthropicAdapter(_ProviderAdapter):
    """Execute requests against Anthropic's Messages API."""

    provider = LLMProvider.ANTHROPIC

    def __init__(self, api_key: str, timeout_s: int) -> None:
        if not api_key:
            msg = "AEAT_LLM_ANTHROPIC_API_KEY must be set for the Anthropic provider."
            raise LLMConfigError(msg)
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_s)

    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request."""

        messages: tuple[MessageParam, ...] = (cast(MessageParam, {"role": "user", "content": request.prompt}),)
        metadata: MetadataParam = {"user_id": request.request_id}
        response: Message | None = None
        try:
            if request.system is None:
                response = await self._client.messages.create(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    messages=messages,
                    metadata=metadata,
                    timeout=request.timeout_s,
                )
            else:
                response = await self._client.messages.create(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    system=request.system,
                    messages=messages,
                    metadata=metadata,
                    timeout=request.timeout_s,
                )
        except RateLimitError as exc:
            headers = exc.response.headers if exc.response is not None else None
            raise_rate_limit("Anthropic rate limit exceeded.", headers.get("retry-after") if headers else None)
        except (AuthenticationError, BadRequestError) as exc:
            raise LLMProviderError(str(exc)) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMProviderError(f"Anthropic connection failure: {exc}") from exc
        except APIStatusError as exc:
            raise LLMProviderError(f"Anthropic API failure ({exc.status_code}).") from exc

        assert response is not None
        text_parts = [block.text for block in response.content if isinstance(block, TextBlock)]
        return ProviderCompletion(
            text="\n".join(part for part in text_parts if part).strip(),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            provider_request_id=response.id,
        )
