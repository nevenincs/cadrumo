"""Error hierarchy for the LLM subpackage.

All public LLM exceptions inherit from
:class:`~llm.LLMError`, which extends
:class:`~core.errors.hierarchy.CadrumoError`. Provider adapters surface
:exc:`~llm.LLMProviderError` and
:exc:`~llm.LLMRateLimitError`, cache and usage storage
surface :exc:`~llm.LLMCacheError`, and strict model
validators surface :exc:`~llm.LLMValidationError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ....core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin

if TYPE_CHECKING:
    from ....application.operator_actions.models import PreconditionVerdict

    _LLMPreconditionErrorMixin = TerminalPreconditionErrorMixin[PreconditionVerdict]
else:
    _LLMPreconditionErrorMixin = TerminalPreconditionErrorMixin


class LLMError(CadrumoError):
    """Base exception for public LLM package failures."""


class LLMProviderError(LLMError):
    """Raised when a provider adapter cannot return a completion."""


class LLMTransientTransportError(LLMProviderError):
    """Raised when a dispatch failed on the way to the model, not at it.

    A connection refused or reset while the runtime loads a model, a 5xx from
    the runtime, a read timeout on a model still coming up: the request never
    produced an answer, and the same request sent again may well produce one.

    Split out of :exc:`~llm.LLMProviderError` because that
    class covers both directions and the retry decision needs them apart. A 4xx
    and a malformed 2xx body are deterministic -- the identical request fails
    identically forever -- so retrying them burns the budget and delays the real
    refusal. Retryability is declared once, on the registered
    :class:`~core.errors.error_codes.ErrorCode` for each class, and the transport reads it
    from there rather than keeping a second list of its own.

    A subclass rather than a sibling, so every existing ``except
    LLMProviderError`` handler keeps catching it: the split refines the
    boundary, it does not move it.
    """


class LLMPdfRasterisationError(LLMError):
    """Raised when :func:`~llm.pdf_rasterisation.rasterise_pdf_pages_to_base64_png` fails."""


class LLMCacheError(LLMError):
    """Raised when :class:`~adapters.persistence.llm.cache.LLMCache` storage fails."""


class LLMRateLimitError(LLMProviderError):
    """Raised when a provider rejects a request because of rate limits.

    Inherits from :exc:`~llm.LLMProviderError` so
    callers can catch all provider-boundary failures together.

    Args:
        message: Human-readable error message.
        retry_after_seconds: Optional server-provided retry delay in seconds.
    """

    def __init__(
        self,
        message: str | None = None,
        retry_after_seconds: float | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(message, context=context, translated_message=translated_message)
        self.retry_after_seconds = retry_after_seconds


class LLMConfigError(_LLMPreconditionErrorMixin, LLMError):
    """Raised when :class:`~llm.LLMClient` configuration is invalid."""


class LLMContentionError(_LLMPreconditionErrorMixin, LLMError):
    """Raised when the agent could not load the selected model with the memory this computer has free.

    The agent's ``model_does_not_fit`` refusal: cadrumo-agent owns load
    admission and decides it when it loads the model. Distinct from
    :exc:`LLMBusyError`, which counts this process's own runs and asks nobody.

    Never retryable. The condition does not decay on a timer -- it decays when
    the load on the computer changes -- so re-sending the same run straight away
    meets the same memory.
    """


class LLMBusyError(_LLMPreconditionErrorMixin, LLMError):
    """Raised when an on-host inference slot is not free and the request is refused.

    Deliberately NOT a subclass of :exc:`~llm.LLMProviderError`: nothing
    failed, and no request reached the agent. This process already has as many
    runs on the local AI as it was configured to have at once.
    """


class LLMConsentError(_LLMPreconditionErrorMixin, LLMError):
    """Raised when an off-host read of taxpayer evidence is refused.

    Deliberately NOT a subclass of
    :exc:`~llm.LLMConfigError`. A configuration fault says
    "you routed this wrongly"; this says "you may not send this document off
    this host", and a caller catching configuration faults to retry at another
    provider must not silently swallow a confidentiality refusal
    (``sensitive-financial-data-secure-storage-only``).
    """


class LLMValidationError(_LLMPreconditionErrorMixin, LLMError):
    """Raised when an LLM-related object fails validation.

    Pydantic field validators translate this registered error to a plain
    ``ValueError`` at their callback boundary while preserving the registered
    error as the cause. Provider and parsing code keeps the typed
    :class:`~llm.LLMError` hierarchy.
    """
