"""Provider adapter contract for the LLM outbound subpackage.

Defines the normalized request and response shapes that every concrete provider
adapter (Anthropic, OpenAI, Gemini, and local) consumes and produces,
so the higher-level :class:`~adapters.outbound.llm.LLMClient` can stay
provider-agnostic. Adapters live in sibling modules under
:mod:`adapters.outbound.llm._providers`.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .._errors import LLMProviderError, LLMRateLimitError
from .._models import LLMProvider


class ProviderRequest(BaseModel):
    """Normalized inbound payload passed to a provider adapter.

    Attributes:
        request_id: Stable opaque hash identifying the public request, suitable
            for cross-referencing cache and usage records.
        model: Fully resolved provider model identifier.
        prompt: Rendered prompt text sent to the provider.
        system: Optional system prompt prepended to the conversation.
        max_tokens: Maximum number of output tokens to request.
        temperature: Sampling temperature in the inclusive range ``[0.0, 1.0]``.
        timeout_s: Per-request timeout in seconds.
        images: Base64-encoded on-host-prepared image inputs for a multimodal
            read (empty for a text-only request). Transient and in-memory only;
            a provider adapter forwards them to a local vision model and they are
            never persisted (sensitive-financial-data-secure-storage-only).
    """

    model_config = ConfigDict(strict=True, frozen=True)

    request_id: str = Field(description="Stable public request hash.")
    model: str = Field(description="Resolved provider model.")
    prompt: str = Field(description="Rendered prompt text.")
    system: str | None = Field(default=None, description="Optional system prompt.")
    max_tokens: int = Field(ge=1, description="Maximum output tokens.")
    temperature: float = Field(ge=0.0, le=1.0, description="Sampling temperature.")
    timeout_s: int = Field(ge=1, description="Per-request timeout in seconds.")
    images: tuple[str, ...] = Field(
        default=(),
        description="Base64-encoded on-host image inputs for a multimodal request; empty for text-only.",
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
    :class:`~adapters.outbound.llm.LLMProvider` and implement
    :meth:`complete` to translate the normalized
    :class:`ProviderRequest` into a vendor-specific call.

    Attributes:
        provider: Identifier of the LLM vendor this adapter speaks to.
    """

    provider: LLMProvider

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


def raise_rate_limit(message: str, retry_after: str | None) -> None:
    """Raise a normalized rate-limit error with parsed retry hint.

    Args:
        message: Human-readable error message to attach.
        retry_after: Raw ``Retry-After`` header value supplied by the provider.

    Raises:
        LLMRateLimitError: Always raised with the parsed retry hint.
    """
    raise LLMRateLimitError(message, retry_after_seconds=parse_retry_after(retry_after))


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
        raise LLMProviderError(f"{provider_name} returned an invalid response.") from exc


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
        raise LLMProviderError(f"{provider_name} returned no {item_name}.")
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
        LLMProviderError: When the request never produced a response
            (connection refused, DNS failure, timeout, protocol error).
    """
    try:
        return await client.post(url, headers=headers, json=json)
    except httpx.RequestError as exc:
        logger.debug("%s connection failure model=%s", provider_name, model, exc_info=True)
        raise LLMProviderError(f"{provider_name} connection failure.") from exc


def check_http_error(response: httpx.Response, *, provider_name: str, model: str, logger: logging.Logger) -> None:
    """Raise a normalized error for a non-2xx LLM HTTP response.

    A 429 raises a rate-limit error carrying the parsed ``Retry-After`` hint;
    any other non-2xx status raises a provider error. Shared by the OpenAI,
    Gemini, and local adapters, whose status-dispatch is otherwise identical.

    Args:
        response: Provider HTTP response to inspect.
        provider_name: Human-readable provider label for log and error text.
        model: Model identifier, included in the log context.
        logger: Adapter logger for status diagnostics.

    Raises:
        LLMRateLimitError: On HTTP 429.
        LLMProviderError: On any other non-2xx status.
    """
    status = response.status_code
    if status == 429:
        logger.warning("%s: rate limit response status=%d model=%s", provider_name, status, model)
        raise_rate_limit(f"{provider_name} rate limit exceeded.", response.headers.get("retry-after"))
    if 200 <= status < 300:
        return
    if status >= 500:
        logger.error("%s: server error status=%d model=%s", provider_name, status, model)
        raise LLMProviderError(f"{provider_name} API failure ({status}).")
    logger.warning("%s: unexpected HTTP status=%d model=%s", provider_name, status, model)
    raise LLMProviderError(f"{provider_name} API failure ({status}).")
