"""Anthropic Messages API adapter for the LLM outbound port.

Implements the
:class:`~llm.providers.base.ProviderAdapter` contract
by translating a normalized
:class:`~llm.providers.base.ProviderRequest` into an
:class:`anthropic.AsyncAnthropic` ``messages.create`` call and converting the
response (or any provider error) into the substrate's typed completion / error
envelope. Network I/O is async; all SDK exceptions are mapped to
:exc:`~llm.LLMProviderError`,
:exc:`~llm.LLMRateLimitError`, or
:exc:`~llm.LLMConfigError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NotRequired, TypedDict, override

from ...core.operator_action_enums import ActionEvidenceProvenance
from ..errors import LLMConfigError, LLMProviderError, LLMTransientTransportError
from ..models import LLMProvider
from ..preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from .base import ProviderAdapter, ProviderCompletion, ProviderRequest, raise_rate_limit

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
        Message,
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
    from ...core.optional_extras import ANTHROPIC_EXTRA, require_optional_extra

    require_optional_extra(ANTHROPIC_EXTRA)

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


class _MessageCreateKwargs(TypedDict):
    """The exact keyword payload sent to ``messages.create``.

    ``system`` and ``temperature`` are ``NotRequired`` because absence here is a
    real wire distinction, not a default: the SDK forwards an explicit ``None``
    as a JSON ``null``, which newer models reject. ``NotRequired`` is precisely
    that claim at the type level, so the payload stays a plain dict the tests can
    assert against while the overload on ``messages.create`` still resolves.
    """

    model: str
    max_tokens: int
    messages: tuple[MessageParam, ...]
    metadata: MetadataParam
    timeout: float
    system: NotRequired[str]
    temperature: NotRequired[float]


def build_message_kwargs(request: ProviderRequest) -> _MessageCreateKwargs:
    """Build the exact keyword arguments sent to ``messages.create``.

    Extracted for the same reason :func:`build_user_content` was: the wire shape
    becomes assertable without an API key, a network call, or a stubbed SDK. A
    parameter's ABSENCE cannot be tested while the payload exists only as
    inlined keyword arguments at the call site, and absence is exactly the claim
    that matters -- a defaulted parameter and an omitted one are different
    requests, and the newer models reject the first.

    Absence is expressed by not adding the key at all, never by passing ``None``:
    the SDK forwards an explicit ``None`` as a JSON ``null``, which is a stated
    value and draws the same rejection the number would.

    Also collapses the system/no-system branch this call site used to duplicate.
    That duplication is why ``temperature`` appeared twice, and why changing it
    once would have left the other path sending it.
    """
    kwargs: _MessageCreateKwargs = {
        "model": request.model,
        "max_tokens": request.max_tokens,
        "messages": ({"role": "user", "content": build_user_content(request)},),
        "metadata": {"user_id": request.request_id},
        "timeout": request.timeout_s,
    }
    if request.system is not None:
        kwargs["system"] = request.system
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    return kwargs


class AnthropicAdapter(ProviderAdapter):
    """Provider adapter that talks to Anthropic's Messages API.

    Holds a bound :class:`anthropic.AsyncAnthropic` client configured with
    the operator's API key and a per-call timeout. The :attr:`provider`
    class attribute identifies this adapter to :class:`~llm.LLMClient`, which
    builds it behind the optional-SDK import boundary -- not to the sibling
    :mod:`adapters.outbound.llm` package, which since the split owns the
    persistence-backed stores and constructs no adapter.

    Attributes:
        provider: The :class:`~llm.LLMProvider` tag
            selecting this adapter.
    """

    provider = LLMProvider.ANTHROPIC
    supports_images = True

    def __init__(self, api_key: str, timeout_s: int) -> None:
        """Construct the adapter and bind a fresh async client.

        Args:
            api_key: Anthropic API key. Empty string raises
                :exc:`~llm.LLMConfigError`.
            timeout_s: Default per-request timeout passed to the SDK.

        Raises:
            LLMConfigError: When ``api_key`` is empty.
        """
        if not api_key:
            raise LLMConfigError(
                context={"provider": self.provider.value, "provider_credentials_present": False},
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.PROVIDER_CREDENTIALS_PRESENT,
                    facts={"provider": self.provider.value, "provider_credentials_present": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
            )
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
            LLMTransientTransportError: On connection and timeout failures, and
                on 5xx API status codes -- the retryable half of the boundary,
                classified here exactly as the httpx adapters classify the same
                two conditions, so the retry decision does not depend on which
                vendor happened to be configured.
            LLMProviderError: On authentication failures, bad requests, and
                other non-2xx API status codes.
        """
        sdk = self._sdk
        # Typed rather than `Any`: the SDK is an optional runtime dependency, but
        # its `Message` record is available to the checker through the
        # TYPE_CHECKING import above, so the response's `content`, `model`,
        # `usage`, and `id` keep their real types instead of being erased.
        response: Message | None = None
        try:
            response = await self._client.messages.create(**build_message_kwargs(request))
        except sdk.RateLimitError as exc:
            # `APIStatusError.__init__` requires `response` and dereferences
            # `response.request` immediately, so it can never be None here.
            headers = exc.response.headers
            raise_rate_limit(
                provider_name=self.provider.value,
                model=request.model,
                retry_after=headers.get("retry-after") if headers else None,
            )
        except (sdk.AuthenticationError, sdk.BadRequestError) as exc:
            raise LLMProviderError(
                context={
                    "provider": self.provider.value,
                    "provider_error_type": type(exc).__name__,
                },
            ) from exc
        except (sdk.APIConnectionError, sdk.APITimeoutError) as exc:
            raise LLMTransientTransportError(
                context={
                    "provider": self.provider.value,
                    "transport_error_type": type(exc).__name__,
                },
            ) from exc
        except sdk.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMTransientTransportError(
                    context={"provider": self.provider.value, "http_status": exc.status_code},
                ) from exc
            raise LLMProviderError(
                context={"provider": self.provider.value, "http_status": exc.status_code},
            ) from exc

        assert response is not None
        text_parts = [block.text for block in response.content if isinstance(block, sdk.TextBlock)]
        return ProviderCompletion(
            text="\n".join(part for part in text_parts if part).strip(),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            provider_request_id=response.id,
        )
