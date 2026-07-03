"""Error hierarchy for the LLM subpackage.

All public LLM exceptions inherit from
:class:`~aeat.adapters.outbound.llm.LLMError`, which extends
:class:`~aeat.core.errors.AeatError`. Provider adapters surface
:exc:`~aeat.adapters.outbound.llm.LLMProviderError` and
:exc:`~aeat.adapters.outbound.llm.LLMRateLimitError`, cache and usage storage
surface :exc:`~aeat.adapters.outbound.llm.LLMCacheError`, and strict model
validators surface :exc:`~aeat.adapters.outbound.llm.LLMValidationError`.
"""

from __future__ import annotations

from ....core.errors import AeatError


class LLMError(AeatError):
    """Base exception for public LLM package failures."""


class LLMProviderError(LLMError):
    """Raised when a provider adapter cannot return a completion."""


class LLMPdfRasterisationError(LLMError):
    """Raised when :func:`~aeat.adapters.outbound.llm.rasterise_pdf_pages_to_base64_png` fails."""


class LLMCacheError(LLMError):
    """Raised when :class:`~aeat.adapters.outbound.llm.LLMCache` storage fails."""


class LLMRateLimitError(LLMProviderError):
    """Raised when a provider rejects a request because of rate limits.

    Inherits from :exc:`~aeat.adapters.outbound.llm.LLMProviderError` so
    callers can catch all provider-boundary failures together.

    Args:
        message: Human-readable error message.
        retry_after_seconds: Optional server-provided retry delay in seconds.
    """

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LLMConfigError(LLMError):
    """Raised when :class:`~aeat.adapters.outbound.llm.LLMClient` configuration is invalid."""


class LLMValidationError(LLMError, ValueError):
    """Raised when an LLM-related object fails validation.

    Inherits from both :class:`~aeat.adapters.outbound.llm.LLMError` and
    :class:`ValueError` to remain compatible with Pydantic's validator-failure
    contract while allowing catch-all
    :class:`~aeat.adapters.outbound.llm.LLMError` handlers to detect integrity
    failures.
    """
