"""Anthropic Messages API adapter for the LLM outbound port.

Implements the
:class:`~adapters.outbound.llm._providers.base._ProviderAdapter` contract
by translating a normalized
:class:`~adapters.outbound.llm._providers.base.ProviderRequest` into an
:class:`anthropic.AsyncAnthropic` ``messages.create`` call and converting the
response (or any provider error) into the substrate's typed completion / error
envelope. Network I/O is async; all SDK exceptions are mapped to
:exc:`~adapters.outbound.llm.LLMProviderError`,
:exc:`~adapters.outbound.llm.LLMRateLimitError`, or
:exc:`~adapters.outbound.llm.LLMConfigError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from .._errors import LLMConfigError, LLMProviderError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, raise_rate_limit

if TYPE_CHECKING:
    # Typing-only: the Anthropic SDK is an optional runtime dependency (the
    # ``anthropic`` extra); the real import stays deferred to
    # :func:`_load_anthropic_sdk` below, gated on ``require_optional_extra``.
    from anthropic import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AsyncAnthropic,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )
    from anthropic.types import (
        ImageBlockParam,
        MessageParam,
        MetadataParam,
        TextBlock,
        TextBlockParam,
    )


@dataclass(frozen=True)
class _AnthropicSdk:
    APIConnectionError: type[APIConnectionError]
    APIStatusError: type[APIStatusError]
    APITimeoutError: type[APITimeoutError]
    AuthenticationError: type[AuthenticationError]
    BadRequestError: type[BadRequestError]
    RateLimitError: type[RateLimitError]
    AsyncAnthropic: type[AsyncAnthropic]
    TextBlock: type[TextBlock]


def _load_anthropic_sdk() -> _AnthropicSdk:
    from ...core import ANTHROPIC_EXTRA, MissingOptionalExtraError, require_optional_extra

    try:
        require_optional_extra(ANTHROPIC_EXTRA)
    except MissingOptionalExtraError as exc:
        raise LLMConfigError(message=str(exc), suggestion=exc.install_hint) from exc

    from anthropic import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AsyncAnthropic,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )
    from anthropic.types import TextBlock

    return _AnthropicSdk(
        APIConnectionError=APIConnectionError,
        APIStatusError=APIStatusError,
        APITimeoutError=APITimeoutError,
        AuthenticationError=AuthenticationError,
        BadRequestError=BadRequestError,
        RateLimitError=RateLimitError,
        AsyncAnthropic=AsyncAnthropic,
        TextBlock=TextBlock,
    )


def build_user_content(request: ProviderRequest) -> str | list[ImageBlockParam | TextBlockParam]:
    """Render one request's user turn as the Messages API expects it.

    A text-only request keeps the bare-string content the API has always
    accepted. A multimodal request becomes a content-block list: one base64
    ``image`` block per input, each declaring the media type its producer
    stamped, followed by a single ``text`` block carrying the prompt.

    Images come BEFORE the text deliberately -- that is the ordering Anthropic
    documents for best results, and it reads correctly too: the question is
    asked about documents the model has already been shown.

    Split out from :meth:`AnthropicAdapter.complete` so the shape can be
    asserted without an API key, a network call, or the optional SDK -- the
    payload is the whole contract here, and a shape defect is invisible in a
    mocked response.

    Args:
        request: Normalized provider request.

    Returns:
        The prompt string when the request carries no images; otherwise the
        image-then-text content-block list.
    """
    if not request.images:
        return request.prompt
    blocks: list[ImageBlockParam | TextBlockParam] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image.media_type.value,
                "data": image.base64_data,
            },
        }
        for image in request.images
    ]
    blocks.append({"type": "text", "text": request.prompt})
    return blocks


class AnthropicAdapter(_ProviderAdapter):
    """Provider adapter that talks to Anthropic's Messages API.

    Holds a bound :class:`anthropic.AsyncAnthropic` client configured with
    the operator's API key and a per-call timeout. The :attr:`provider`
    class attribute identifies this adapter to the :mod:`adapters.outbound.llm`
    factory.

    Attributes:
        provider: The :class:`~adapters.outbound.llm.LLMProvider` tag
            selecting this adapter.
    """

    provider = LLMProvider.ANTHROPIC
    supports_images = True

    def __init__(self, api_key: str, timeout_s: int) -> None:
        """Construct the adapter and bind a fresh async client.

        Args:
            api_key: Anthropic API key. Empty string raises
                :exc:`~adapters.outbound.llm.LLMConfigError`.
            timeout_s: Default per-request timeout passed to the SDK.

        Raises:
            LLMConfigError: When ``api_key`` is empty.
        """
        if not api_key:
            msg = "CADRUMO_LLM_ANTHROPIC_API_KEY must be set for the Anthropic provider."
            raise LLMConfigError(msg)
        self._sdk = _load_anthropic_sdk()
        self._client = self._sdk.AsyncAnthropic(api_key=api_key, timeout=timeout_s)

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
        sdk = self._sdk
        user_message: MessageParam = {"role": "user", "content": build_user_content(request)}
        messages = (user_message,)
        metadata: MetadataParam = {"user_id": request.request_id}
        response: Any = None
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
        except sdk.RateLimitError as exc:
            headers = exc.response.headers if exc.response is not None else None
            raise_rate_limit("Anthropic rate limit exceeded.", headers.get("retry-after") if headers else None)
        except (sdk.AuthenticationError, sdk.BadRequestError) as exc:
            raise LLMProviderError(str(exc)) from exc
        except (sdk.APIConnectionError, sdk.APITimeoutError) as exc:
            raise LLMProviderError(f"Anthropic connection failure: {exc}") from exc
        except sdk.APIStatusError as exc:
            raise LLMProviderError(f"Anthropic API failure ({exc.status_code}).") from exc

        assert response is not None
        text_parts = [block.text for block in response.content if isinstance(block, sdk.TextBlock)]
        return ProviderCompletion(
            text="\n".join(part for part in text_parts if part).strip(),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            provider_request_id=response.id,
        )
