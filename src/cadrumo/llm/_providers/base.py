"""Provider adapter contract for the LLM outbound subpackage.

Defines the normalized request and response shapes that every concrete provider
adapter (Anthropic, OpenAI, Gemini, and local) consumes and produces,
so the higher-level :class:`~llm.LLMClient` can stay
provider-agnostic. Adapters live in sibling modules under
:mod:`llm._providers`.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...core import ActionEvidenceProvenance
from ..errors import LLMConfigError, LLMProviderError, LLMRateLimitError, LLMTransientTransportError
from .._models import LLMProvider, MultimodalImageInput
from .._preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

if TYPE_CHECKING:
    from logging import Logger


class ProviderRequest(BaseModel):
    """Normalized inbound payload passed to a provider adapter.

    Attributes:
        request_id: Stable opaque hash identifying the public request, suitable
            for cross-referencing cache and usage records.
        model: Fully resolved provider model identifier.
        prompt: Rendered prompt text sent to the provider.
        system: Optional system prompt prepended to the conversation.
        max_tokens: Maximum number of output tokens to request.
        temperature: Sampling temperature in the inclusive range ``[0.0, 1.0]``,
            or ``None`` meaning the parameter is OMITTED from the wire rather
            than sent at some default. The distinction is load-bearing: a
            vendor's newer models reject an explicitly-sent ``temperature``
            with a 400, so "no preference" cannot be expressed as a number.
        timeout_s: Per-request timeout in seconds.
        images: On-host-prepared image inputs for a multimodal read (empty for a
            text-only request), each carrying its base64 payload AND its declared
            media type -- a cloud provider needs the type on the wire, so the
            adapter cannot receive a bare string. Transient and in-memory only;
            an adapter forwards them to a vision model and they are never
            persisted (sensitive-financial-data-secure-storage-only).
    """

    model_config = ConfigDict(strict=True, frozen=True)

    request_id: str = Field(description="Stable public request hash.")
    model: str = Field(description="Resolved provider model.")
    prompt: str = Field(description="Rendered prompt text.")
    system: str | None = Field(default=None, description="Optional system prompt.")
    max_tokens: int = Field(ge=1, description="Maximum output tokens.")
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Sampling temperature, or None to omit the parameter entirely.",
    )
    timeout_s: int = Field(ge=1, description="Per-request timeout in seconds.")
    images: tuple[MultimodalImageInput, ...] = Field(
        default=(),
        description="On-host image inputs for a multimodal request; empty for text-only.",
    )


class ProviderCompletion(BaseModel):
    """Normalized provider response returned to the public client.

    Attributes:
        text: Generated text payload.
        model: Provider model that actually served the request (may differ from
            the requested model when a vendor performs upstream routing).
        input_tokens: Provider-reported prompt token count.
        output_tokens: Provider-reported output token count.
        provider_request_id: Provider-native request or message id when
            available, otherwise ``None``.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    text: str = Field(description="Generated text.")
    model: str = Field(description="Provider model that served the request.")
    input_tokens: int = Field(ge=0, description="Provider-reported prompt token count.")
    output_tokens: int = Field(ge=0, description="Provider-reported output token count.")
    provider_request_id: str | None = Field(default=None, description="Provider-native request or message id.")


class _ProviderAdapter(ABC):
    """Private interface every concrete provider adapter implements.

    Concrete subclasses bind :attr:`provider` to a member of
    :class:`~llm.LLMProvider` and implement
    :meth:`complete` to translate the normalized
    :class:`ProviderRequest` into a vendor-specific call.

    Attributes:
        provider: Identifier of the LLM vendor this adapter speaks to.
        supports_images: Whether :meth:`complete` actually forwards
            :attr:`ProviderRequest.images` to the vendor. Declared as DATA on
            the class rather than left to each adapter to remember, and
            enforced once at the client's single dispatch point -- the same
            reasoning :func:`post_provider_request` documents for the transport
            boundary. Defaults to ``False`` so a newly added adapter is
            text-only until it has genuinely implemented the image path; the
            failure of the opposite default is silent and unbounded.
    """

    provider: LLMProvider
    supports_images: bool = False
    _api_key: str
    _timeout_s: int

    def _configure_api_key(self, api_key: str, timeout_s: int) -> None:
        """Bind credentials and timeout for an API-key-backed provider."""
        if not api_key:
            raise LLMConfigError(
                context={"provider": self.provider.value, "provider_credentials_present": False},
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.PROVIDER_CREDENTIALS_PRESENT,
                    facts={"provider": self.provider.value, "provider_credentials_present": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
            )
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def _request_completion[ResponseModel: BaseModel](
        self,
        request: ProviderRequest,
        *,
        endpoint: str,
        headers: Mapping[str, str] | None,
        json: object,
        response_model: type[ResponseModel],
        logger: Logger,
    ) -> ResponseModel:
        """Send and validate one HTTP provider completion response."""
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await post_provider_request(
                client,
                endpoint,
                provider_name=self.provider.value,
                model=request.model,
                logger=logger,
                headers=headers,
                json=json,
            )
        check_http_error(response, provider_name=self.provider.value, model=request.model, logger=logger)
        return parse_provider_response(
            response,
            provider_name=self.provider.value,
            response_model=response_model,
        )

    def unsupported_parameters(self, model: str) -> frozenset[str]:
        """Return the request parameters this adapter must NOT put on the wire for *model*.

        The second half of the capability axis :attr:`supports_images` opened.
        Both defects are one shape -- a request field the transport assumed was
        universal -- and they failed in opposite directions: ``images`` was
        silently DROPPED by adapters that could not carry it, and
        ``temperature`` is unconditionally SENT to models that reject it. One
        was dropped without telling anyone; one is sent without asking.

        Declared per MODEL rather than per adapter because that is where vendors
        actually differ: the same Anthropic adapter serves models that accept
        ``temperature`` and models that refuse it, so an adapter-wide flag
        cannot express the constraint.

        Defaults to the empty set -- an adapter carries every parameter until it
        declares otherwise. That is the opposite default from
        :attr:`supports_images`, deliberately: silently dropping an image makes
        a model answer from nothing, which is unbounded harm, while omitting a
        sampling parameter falls back to the vendor's own default. The
        restrictive default belongs where the failure is silent, not where it is
        merely a different temperature.
        """
        del model
        return frozenset[str]()

    @abstractmethod
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request against the underlying provider.

        Args:
            request: Normalized request payload.

        Returns:
            Normalized :class:`ProviderCompletion` response.
        """


def parse_retry_after(value: str | None) -> float | None:
    """Parse an HTTP ``Retry-After`` header value into seconds.

    Args:
        value: Raw header value, or ``None`` when the header is absent.

    Returns:
        Finite, non-negative seconds to wait, or ``None`` when the value is
        missing or cannot represent a safe delay.
    """
    if value is None:
        return None
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def raise_rate_limit(*, provider_name: str, model: str, retry_after: str | None) -> None:
    """Raise a normalized rate-limit error with parsed retry hint.

    Args:
        provider_name: Stable provider identity observed at the transport boundary.
        model: Model identifier carried by the rejected request.
        retry_after: Raw ``Retry-After`` header value supplied by the provider.

    Raises:
        LLMRateLimitError: Always raised with the parsed retry hint.
    """
    parsed_retry_after = parse_retry_after(retry_after)
    context: dict[str, str | float | int | bool] = {
        "provider_name": provider_name,
        "model": model,
        "http_status": 429,
    }
    if parsed_retry_after is not None:
        context["retry_after_seconds"] = parsed_retry_after
    raise LLMRateLimitError(retry_after_seconds=parsed_retry_after, context=context)


def parse_provider_response[ProviderResponse: BaseModel](
    response: httpx.Response,
    *,
    provider_name: str,
    response_model: type[ProviderResponse],
) -> ProviderResponse:
    """Validate a successful provider response at the outbound boundary.

    Args:
        response: Successful HTTP response whose JSON body must match the provider schema.
        provider_name: Human-readable provider label for the public error.
        response_model: Strict Pydantic model for the provider response envelope.

    Returns:
        The validated provider response.

    Raises:
        LLMProviderError: When a 2xx response body is malformed for its provider.
    """
    try:
        return response_model.model_validate_json(response.text)
    except ValidationError as exc:
        raise LLMProviderError(
            context={
                "provider_name": provider_name,
                "provider_response_valid": False,
                "provider_response_error_type": type(exc).__name__,
            },
        ) from exc


def require_provider_response_item[ProviderResponseItem](
    items: tuple[ProviderResponseItem, ...],
    *,
    provider_name: str,
    item_name: str,
) -> ProviderResponseItem:
    """Return the first required response item or raise a declared provider error.

    Args:
        items: Provider response collection expected to contain a primary item.
        provider_name: Human-readable provider label for the public error.
        item_name: Plural provider-specific item name used in diagnostics.

    Returns:
        The first response item.

    Raises:
        LLMProviderError: When a successful provider response has no primary item.
    """
    if not items:
        raise LLMProviderError(
            context={
                "provider_name": provider_name,
                "provider_response_item_present": False,
                "provider_response_item_kind": item_name,
            },
        )
    return items[0]


async def post_provider_request(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider_name: str,
    model: str,
    logger: logging.Logger,
    headers: Mapping[str, str] | None = None,
    json: object,
) -> httpx.Response:
    """POST to a provider endpoint, mapping transport failure to the typed boundary.

    ``LLMProviderError`` is the declared transport/provider boundary of this
    subpackage, and the Anthropic adapter maps its SDK's connection and timeout
    failures onto it. The httpx-based adapters did not agree: Gemini caught
    :exc:`httpx.RequestError` while OpenAI and the local runtime called
    ``client.post`` bare, so an unreachable endpoint surfaced as a raw
    ``ConnectError`` / ``ConnectTimeout`` from two of the four providers. The
    error TYPE, and therefore every caller's recovery path, depended on which
    provider happened to be configured — for one and the same failure.

    Routing every httpx provider through this one call makes the boundary a
    property of the transport rather than of each adapter's memory to catch,
    and keeps the provider context (name, model) attached to the failure.

    Args:
        client: The provider adapter's own ``httpx.AsyncClient``.
        url: Fully resolved endpoint.
        provider_name: Human-readable provider label for log and error text.
        model: Model identifier, included in the log context.
        logger: Adapter logger for transport diagnostics.
        headers: Optional request headers (auth material, API keys).
        json: JSON-serialisable request body.

    Returns:
        The provider's :class:`httpx.Response`, unexamined — status dispatch
        remains :func:`check_http_error`'s job.

    Raises:
        LLMTransientTransportError: When the request never produced a response
            (connection refused, DNS failure, timeout, protocol error). Typed as
            the TRANSIENT half of the boundary because that is what the failure
            is: nothing was decided at the model, and a local runtime that is
            still loading a multi-gigabyte model refuses connections for exactly
            as long as the load takes. ``httpx.TimeoutException`` is a
            ``RequestError`` subclass, so a read timeout arrives here too.
    """
    try:
        return await client.post(url, headers=headers, json=json)
    except httpx.RequestError as exc:
        logger.debug("%s connection failure model=%s", provider_name, model, exc_info=True)
        raise LLMTransientTransportError(
            context={
                "provider_name": provider_name,
                "model": model,
                "transport_error_type": type(exc).__name__,
            },
        ) from exc


def check_http_error(response: httpx.Response, *, provider_name: str, model: str, logger: logging.Logger) -> None:
    """Raise a normalized error for a non-2xx LLM HTTP response.

    A 429 raises a rate-limit error carrying the parsed ``Retry-After`` hint;
    any other non-2xx status raises a provider error. Shared by the OpenAI,
    Gemini, and local adapters, whose status-dispatch is otherwise identical.

    The 5xx and 4xx branches raise DIFFERENT types, and the split is the whole
    basis of the retry decision. A 5xx is the server saying it failed to answer
    a request it accepted, which the same request may survive on a second
    attempt; a 4xx is the server saying the request itself is wrong, which the
    same request will never survive. Retrying the second kind spends a bounded
    budget on a certainty and delays the real refusal.

    Args:
        response: Provider HTTP response to inspect.
        provider_name: Human-readable provider label for log and error text.
        model: Model identifier, included in the log context.
        logger: Adapter logger for status diagnostics.

    Raises:
        LLMRateLimitError: On HTTP 429.
        LLMTransientTransportError: On any 5xx status.
        LLMProviderError: On any other non-2xx status.
    """
    status = response.status_code
    if status == 429:
        logger.warning("%s: rate limit response status=%d model=%s", provider_name, status, model)
        raise_rate_limit(provider_name=provider_name, model=model, retry_after=response.headers.get("retry-after"))
    if 200 <= status < 300:
        return
    if status >= 500:
        logger.error("%s: server error status=%d model=%s", provider_name, status, model)
        raise LLMTransientTransportError(
            context={"provider_name": provider_name, "model": model, "http_status": status},
        )
    logger.warning("%s: unexpected HTTP status=%d model=%s", provider_name, status, model)
    raise LLMProviderError(
        context={"provider_name": provider_name, "model": model, "http_status": status},
    )
