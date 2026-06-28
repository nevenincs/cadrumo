"""Anthropic Messages API adapter for the LLM outbound port.

Implements the :class:`aeat.adapters.outbound.llm._providers.base._ProviderAdapter`
contract by translating a normalized :class:`aeat.adapters.outbound.llm._providers.base.ProviderRequest`
into an :class:`anthropic.AsyncAnthropic` ``messages.create`` call and
converting the response (or any provider error) into the substrate's
typed completion / error envelope. Network I/O is async; all SDK
exceptions are mapped to :exc:`aeat.adapters.outbound.llm._errors.LLMProviderError`,
:exc:`aeat.adapters.outbound.llm._errors.LLMRateLimitError`, or
:exc:`aeat.adapters.outbound.llm._errors.LLMConfigError`.
"""

from __future__ import annotations

from typing import override

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
    """Provider adapter that talks to Anthropic's Messages API.

    Holds a bound :class:`anthropic.AsyncAnthropic` client configured with
    the operator's API key and a per-call timeout. The :attr:`provider`
    class attribute identifies this adapter to the :mod:`aeat.adapters.outbound.llm`
    factory.

    Attributes:
        provider: The :class:`aeat.adapters.outbound.llm._models.LLMProvider`
            tag selecting this adapter.
    """

    provider = LLMProvider.ANTHROPIC

    def __init__(self, api_key: str, timeout_s: int) -> None:
        """Construct the adapter and bind a fresh async client.

        Args:
            api_key: Anthropic API key. Empty string raises
                :exc:`aeat.adapters.outbound.llm._errors.LLMConfigError`.
            timeout_s: Default per-request timeout passed to the SDK.

        Raises:
            LLMConfigError: When ``api_key`` is empty.
        """
        if not api_key:
            msg = "AEAT_LLM_ANTHROPIC_API_KEY must be set for the Anthropic provider."
            raise LLMConfigError(msg)
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_s)

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request against Anthropic and normalize the result.

        Issues a ``messages.create`` call (with or without a ``system``
        prompt), concatenates every :class:`anthropic.types.TextBlock` in
        the response, and returns a :class:`ProviderCompletion`. SDK
        errors are mapped to the substrate's typed exception hierarchy.

        Args:
            request: Normalized provider request carrying the model id,
                prompt, optional system prompt, sampling parameters, and
                a request-id used as Anthropic ``metadata.user_id``.

        Returns:
            A :class:`ProviderCompletion` with the joined text, model id
            echoed by the server, token usage, and the provider's request id.

        Raises:
            LLMProviderError: On authentication failures, bad requests, connection
                or timeout failures, and non-2xx API status codes.
        """
        user_message: MessageParam = {"role": "user", "content": request.prompt}
        messages: tuple[MessageParam, ...] = (user_message,)
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
