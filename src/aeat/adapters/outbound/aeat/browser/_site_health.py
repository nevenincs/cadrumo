"""Strict pydantic v2 records for AEAT site-health detection.

The site-health layer classifies AEAT Sede Electrónica responses into a
closed set of states (:class:`SiteHealthState`) so that a planned
mantenimiento, a WAF challenge, or an HTTP 429/503 rate-limit answer
becomes a first-class typed signal instead of an opaque DOM parse
error collapsing into ``UNHANDLED_EXCEPTION`` somewhere downstream.

Every record in this module is frozen, strict, ``extra="forbid"``
pydantic v2. The closed state catalogue is an :class:`enum.StrEnum`.
Collections are ``tuple[str, ...]`` — list containers are forbidden on
frozen models per project convention.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
)

from ._errors import BrowserValidationError


class SiteHealthState(StrEnum):
    """Closed catalogue of AEAT site-health classifications.

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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class SiteHealthEvidence(_SiteHealthRecord):
    """Bounded evidence block captured alongside a classification.

    Attributes:
        url: The probe URL whose response was classified.
        http_status: HTTP status observed on the response. Bounded to
            ``[100, 599]``; transport-level failures use ``599`` as a
            sentinel and annotate ``detected_markers`` accordingly.
        html_fragment: At most 4096 characters of the response body,
            captured for diagnostic logs. The bound keeps error logs
            sane and avoids leaking full response bodies.
        detected_markers: Frozen tuple of the substrings (or
            structured keys such as ``retry-after:30``) that led the
            parser to its verdict. Each marker is bounded between 1
            and 128 characters.
    """

    url: AnyHttpUrl
    http_status: int = Field(ge=100, le=599)
    html_fragment: str = Field(max_length=4096)
    detected_markers: tuple[str, ...]

    @field_validator("detected_markers")
    @classmethod
    def _validate_markers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Enforce per-item length bounds on every detected marker."""
        for marker in value:
            if not isinstance(marker, str):
                raise TypeError(f"detected_markers entries must be str, got {type(marker).__name__}")
            if len(marker) < 1 or len(marker) > 128:
                raise BrowserValidationError(f"detected_markers entry must be 1..128 chars, got length {len(marker)}")
        return value


class SiteHealthStatus(_SiteHealthRecord):
    """Full classification record for a single probe.

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


def validate_site_health_url(url: str) -> AnyHttpUrl:
    """Validate a URL for site-health evidence records."""

    return _URL_ADAPTER.validate_python(url)
