"""Error hierarchy for the LLM subpackage.

All public LLM exceptions inherit from
:class:`~llm.LLMError`, which extends
:class:`~core.errors.CadrumoError`. Provider adapters surface
:exc:`~llm.LLMProviderError` and
:exc:`~llm.LLMRateLimitError`, cache and usage storage
surface :exc:`~llm.LLMCacheError`, and strict model
validators surface :exc:`~llm.LLMValidationError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ..core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin

if TYPE_CHECKING:
    from ..application.operator_actions._models import PreconditionVerdict

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
    :class:`~core.errors.ErrorCode` for each class, and the transport reads it
    from there rather than keeping a second list of its own.

    A subclass rather than a sibling, so every existing ``except
    LLMProviderError`` handler keeps catching it: the split refines the
    boundary, it does not move it.
    """


class LLMPdfRasterisationError(LLMError):
    """Raised when :func:`~llm.rasterise_pdf_pages_to_base64_png` fails."""


class LLMCacheError(LLMError):
    """Raised when :class:`~adapters.outbound.llm.LLMCache` storage fails."""


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
    """Raised when this machine has no measured headroom to load the model.

    The other half of admission control, and a different question from
    :exc:`LLMBusyError`. Occupancy asks how many loads are already running;
    this asks whether ONE load fits right now, measured against free memory
    rather than counted. Both can refuse while the other would admit.

    Fails closed on an unreadable figure, because "could not tell" is not
    evidence of headroom and is precisely the state that destroys running work
    on a machine with no spare device memory.

    Never retryable. The condition does not decay on a timer -- it decays when
    the load on the machine changes -- so re-sending on a schedule turns one
    refusal into several while the memory it is waiting for is still held.
    """


class LLMBusyError(_LLMPreconditionErrorMixin, LLMError):
    """Raised when an on-host inference slot is not free and the request is refused.

    The admission half of the local-resource boundary, and deliberately NOT a
    subclass of :exc:`~llm.LLMProviderError`: nothing failed,
    and no request reached a runtime. The machine is already running as much
    inference as it was configured to run at once, and a second concurrent load
    on consumer hardware is an out-of-memory kill that takes the FIRST read down
    with it.

    Distinct from a contention refusal, which reports measured headroom against
    one model's requirement. This one reports occupancy: the arena is full
    regardless of what the figures say, because two loads that each fit
    individually still do not fit together.
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


class LLMValidationError(_LLMPreconditionErrorMixin, LLMError, ValueError):
    """Raised when an LLM-related object fails validation.

    Inherits from both :class:`~llm.LLMError` and
    :class:`ValueError` to remain compatible with Pydantic's validator-failure
    contract while allowing catch-all
    :class:`~llm.LLMError` handlers to detect integrity
    failures.
    """
