"""Error hierarchy for the LLM subpackage."""

from __future__ import annotations

from ....core.errors import AeatError


class LLMError(AeatError):
    """Base exception for LLM package failures."""


class LLMProviderError(LLMError):
    """Raised when a provider returns an unrecoverable error."""


class LLMCacheError(LLMError):
    """Raised when a cache entry cannot be read, written, or parsed."""


class LLMRateLimitError(LLMProviderError):
    """Raised when a provider rejects a request because of rate limits.

    Args:
        message: Human-readable error message.
        retry_after_seconds: Optional server-provided retry delay in seconds.
    """

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LLMConfigError(LLMError):
    """Raised when the LLM client configuration is invalid or incomplete."""
