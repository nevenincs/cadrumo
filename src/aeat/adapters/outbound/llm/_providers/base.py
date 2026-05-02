"""Provider adapter contract for the LLM outbound subpackage.

Defines the normalized request and response shapes that every concrete provider
adapter (Anthropic, OpenAI, Gemini, local, deterministic) consumes and produces,
so the higher-level :class:`aeat.adapters.outbound.llm.LLMClient` can stay
provider-agnostic. Adapters live in sibling modules under
:mod:`aeat.adapters.outbound.llm._providers`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from .._errors import LLMRateLimitError
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
    """

    model_config = ConfigDict(strict=True, frozen=True)

    request_id: str = Field(description="Stable public request hash.")
    model: str = Field(description="Resolved provider model.")
    prompt: str = Field(description="Rendered prompt text.")
    system: str | None = Field(default=None, description="Optional system prompt.")
    max_tokens: int = Field(ge=1, description="Maximum output tokens.")
    temperature: float = Field(ge=0.0, le=1.0, description="Sampling temperature.")
    timeout_s: int = Field(ge=1, description="Per-request timeout in seconds.")


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
            Normalized completion response.
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
        :exc:`aeat.adapters.outbound.llm.LLMRateLimitError`: Always raised.
    """

    raise LLMRateLimitError(message, retry_after_seconds=parse_retry_after(retry_after))
