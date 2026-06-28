"""Provider adapter contract for the LLM outbound subpackage.

Defines the normalized request and response shapes that every concrete provider
adapter (Anthropic, OpenAI, Gemini, local, deterministic) consumes and produces,
so the higher-level :class:`aeat.adapters.outbound.llm.LLMClient` can stay
provider-agnostic. Adapters live in sibling modules under
:mod:`aeat.adapters.outbound.llm._providers`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from .._errors import LLMProviderError, LLMRateLimitError
from .._models import LLMProvider

if TYPE_CHECKING:
    import httpx


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
    :class:`aeat.adapters.outbound.llm._models.LLMProvider` and implement
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
        Number of seconds to wait, or ``None`` when the value is missing or
        not a plain numeric string.
    """
    if value is None:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def raise_rate_limit(message: str, retry_after: str | None) -> None:
    """Raise a normalized rate-limit error with parsed retry hint.

    Args:
        message: Human-readable error message to attach.
        retry_after: Raw ``Retry-After`` header value supplied by the provider.

    Raises:
        LLMRateLimitError: Always raised with the parsed retry hint.
    """
    raise LLMRateLimitError(message, retry_after_seconds=parse_retry_after(retry_after))


def check_http_error(response: httpx.Response, *, provider_name: str, model: str, logger: logging.Logger) -> None:
    """Raise a normalized error for a non-2xx LLM HTTP response.

    A 429 raises a rate-limit error carrying the parsed ``Retry-After`` hint;
    any other 5xx or 4xx status raises a provider error. Shared by the OpenAI
    and Gemini adapters, whose status-dispatch was otherwise identical.

    Args:
        response: Provider HTTP response to inspect.
        provider_name: Human-readable provider label for log and error text.
        model: Model identifier, included in the log context.
        logger: Adapter logger for status diagnostics.

    Raises:
        LLMRateLimitError: On HTTP 429.
        LLMProviderError: On any other 5xx or 4xx status.
    """
    status = response.status_code
    if status == 429:
        logger.warning("%s: rate limit response status=%d model=%s", provider_name, status, model)
        raise_rate_limit(f"{provider_name} rate limit exceeded.", response.headers.get("retry-after"))
    if status >= 500:
        logger.error("%s: server error status=%d model=%s", provider_name, status, model)
        raise LLMProviderError(f"{provider_name} API failure ({status}).")
    if status >= 400:
        logger.warning("%s: client error status=%d model=%s", provider_name, status, model)
        raise LLMProviderError(f"{provider_name} API failure ({status}).")
