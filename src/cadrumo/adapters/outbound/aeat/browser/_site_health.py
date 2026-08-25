"""Strict records for AEAT site-health detection.

The site-health layer classifies AEAT Sede Electrónica responses into a
closed :class:`SiteHealthState` catalogue. A planned mantenimiento page,
WAF challenge, HTTP 429/503 rate-limit answer, or transport failure becomes a
typed :class:`SiteHealthStatus` instead of collapsing into a generic browser
or workflow exception.

Every record in this module is frozen, strict, ``extra="forbid"`` pydantic v2.
The closed state catalogue is an :class:`enum.StrEnum`. Collections are
``tuple[str, ...]`` so evidence remains immutable after classification.

See Also:
    :func:`adapters.outbound.aeat.browser._site_health_parsers.evaluate_response`
        Pure parser entry point that creates :class:`SiteHealthStatus` records
        from HTTP status, headers, and body text.
    :meth:`adapters.outbound.aeat.browser.BrowserSession.navigate`
        Browser navigation hook that raises
        :class:`core.errors.SiteHealthError` when a non-OK status is
        classified.
    :class:`core.errors.SiteHealthStatusLike`
        Core-layer structural view that lets application workflow and
        diagnostics consume these adapter records without importing them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    Field,
    TypeAdapter,
    field_validator,
)

from .....core import STRICT_FROZEN_CONFIG
from .....core.redaction import redact_for_log
from .errors import BrowserValidationError

_MAX_HTML_FRAGMENT_CHARS: Final = 4096


class SiteHealthState(StrEnum):
    """Closed catalogue of AEAT site-health classifications.

    Parser functions emit these states inside :class:`SiteHealthStatus`.
    :class:`~core.errors.SiteHealthError` then carries non-OK states across
    the browser/application boundary.

    Values:
        OK: No anomaly detected; the response looks like a healthy
            AEAT page.
        MANTENIMIENTO: A scheduled / unplanned maintenance banner or
            interstitial was detected.
        WAF_CHALLENGE: A Web Application Firewall rejection or
            challenge page (``Request blocked``, reference / support
            IDs, etc.).
        RATE_LIMITED: Server answered with HTTP 429 or 503 indicating
            the caller is being throttled.
        UNREACHABLE: Transport-level failure (DNS, TCP, TLS,
            Playwright navigation timeout) before a response body
            could be inspected.
        UNKNOWN_ERROR: Reserved for future unclassified failures; no
            parser currently emits this state.
    """

    OK = "ok"
    MANTENIMIENTO = "mantenimiento"
    WAF_CHALLENGE = "waf_challenge"
    RATE_LIMITED = "rate_limited"
    UNREACHABLE = "unreachable"
    UNKNOWN_ERROR = "unknown_error"


class _SiteHealthRecord(BaseModel):
    """Common config base for every site-health wire record.

    Mirrors the status-record convention used by AEAT status readers:
    strict typing, frozen instances, and ``extra="forbid"`` so any
    unexpected field is a parse error rather than a silent
    pass-through.
    """

    model_config = STRICT_FROZEN_CONFIG


class SiteHealthEvidence(_SiteHealthRecord):
    """Bounded evidence block captured alongside a classification.

    Evidence is diagnostic, not a full response archive. The HTML fragment is
    redacted and bounded before it is stored, while ``detected_markers`` keeps
    the exact marker keys that caused the parser to choose a
    :class:`SiteHealthState`.

    Attributes:
        url: The probe URL whose response was classified.
        http_status: HTTP status observed on the response. Bounded to
            ``[100, 599]``; transport-level failures use ``599`` as a
            sentinel and annotate ``detected_markers`` accordingly.
        html_fragment: At most 4096 characters of redacted response
            body, captured for diagnostic logs. The bound keeps error
            logs sane and avoids leaking full response bodies.
        detected_markers: Frozen tuple of the substrings (or
            structured keys such as ``retry-after:30``) that led the
            parser to its verdict. Each marker is bounded between 1
            and 128 characters.
    """

    url: AnyHttpUrl
    http_status: int = Field(ge=100, le=599)
    html_fragment: str = Field(max_length=_MAX_HTML_FRAGMENT_CHARS)
    detected_markers: tuple[str, ...]

    @field_validator("html_fragment")
    @classmethod
    def _redact_html_fragment(cls, value: str) -> str:
        """Apply the central log redaction policy to diagnostic HTML."""
        return redact_for_log(value)[:_MAX_HTML_FRAGMENT_CHARS]

    @field_validator("detected_markers")
    @classmethod
    def _validate_markers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Enforce per-item length bounds on every detected marker."""
        for marker in value:
            if not isinstance(marker, str):
                raise ValueError(f"detected_markers entries must be str, got {type(marker).__name__}")
            if len(marker) < 1 or len(marker) > 128:
                raise BrowserValidationError(f"detected_markers entry must be 1..128 chars, got length {len(marker)}")
        return value


class SiteHealthStatus(_SiteHealthRecord):
    """Full classification record for a single probe.

    Produced by the parser suite and by
    :meth:`adapters.outbound.aeat.browser.BrowserSession.navigate` for
    transport failures. Non-OK records are carried by
    :class:`core.errors.SiteHealthError`; diagnostics and workflow code
    then inspect this record instead of re-parsing response bodies.

    Attributes:
        state: The detected :class:`SiteHealthState`.
        evidence: Bounded :class:`SiteHealthEvidence` describing the
            response that was classified.
        observed_at: Timezone-aware timestamp when the classification
            was produced.
        retry_after_seconds: Optional positive integer derived from a
            ``Retry-After`` header or the rate-limit default when the
            state is :attr:`SiteHealthState.RATE_LIMITED`.
    """

    state: SiteHealthState
    evidence: SiteHealthEvidence
    observed_at: AwareDatetime
    retry_after_seconds: int | None = Field(default=None, ge=1)


_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
"""Module-level adapter used by parser call sites to validate URLs."""
