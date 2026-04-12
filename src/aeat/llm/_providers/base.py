"""Private provider adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from aeat.llm._errors import LLMRateLimitError
from aeat.llm._models import LLMProvider


class ProviderRequest(BaseModel):
    """Normalized provider request."""

    model_config = ConfigDict(strict=True, frozen=True)

    request_id: str = Field(description="Stable public request hash.")
    model: str = Field(description="Resolved provider model.")
    prompt: str = Field(description="Rendered prompt text.")
    system: str | None = Field(default=None, description="Optional system prompt.")
    max_tokens: int = Field(ge=1, description="Maximum output tokens.")
    temperature: float = Field(ge=0.0, le=1.0, description="Sampling temperature.")
    timeout_s: int = Field(ge=1, description="Per-request timeout in seconds.")


class ProviderCompletion(BaseModel):
    """Normalized provider response."""

    model_config = ConfigDict(strict=True, frozen=True)

    text: str = Field(description="Generated text.")
    model: str = Field(description="Provider model that served the request.")
    input_tokens: int = Field(ge=0, description="Provider-reported prompt token count.")
    output_tokens: int = Field(ge=0, description="Provider-reported output token count.")
    provider_request_id: str | None = Field(default=None, description="Provider-native request or message id.")


class _ProviderAdapter(ABC):
    """Private interface implemented by every provider adapter."""

    provider: LLMProvider

    @abstractmethod
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request against the provider."""


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header into seconds, if possible."""

    if value is None:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def raise_rate_limit(message: str, retry_after: str | None) -> None:
    """Raise a normalized rate-limit error."""

    raise LLMRateLimitError(message, retry_after_seconds=parse_retry_after(retry_after))
