"""Marker-based parsers for AEAT site-health classification.

Three pure functions inspect the HTTP status, headers, and body of a response
and decide whether it looks like AEAT maintenance, a Web Application Firewall
challenge, or a rate-limit response. :func:`evaluate_response` runs them in a
deterministic order and returns the first non-``None``
:class:`SiteHealthStatus`.

The parsers are deliberately synchronous, side-effect free, and free of any
Playwright dependency. :func:`adapters.outbound.aeat.browser._site_health_probe.probe_response`
is the adapter boundary used by
:meth:`adapters.outbound.aeat.browser.BrowserSession.navigate`; it turns
navigation responses into :class:`SiteHealthStatus` records that can be carried
by :class:`core.errors.SiteHealthError`. The marker corpora reflect the
observed mantenimiento, WAF, and rate-limit responses on AEAT Sede Electrónica.

See Also:
    :class:`adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
        Frozen record returned by every positive parser classification.
    :class:`core.errors.SiteHealthState`
        Closed state catalogue emitted by this parser suite.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from .....core.errors.hierarchy import SiteHealthState
from .....core.time.clock import now
from .....core.time.utc import coerce_utc_aware
from ._site_health import (
    SiteHealthEvidence,
    SiteHealthStatus,
    parse_site_health_url,
)

_MAX_FRAGMENT_CHARS = 4096

_MANTENIMIENTO_MARKERS: tuple[str, ...] = (
    "mantenimiento",
    "interrupcion del servicio",
    "estamos realizando tareas de mantenimiento",
    "sede electronica no disponible",
    "disculpe las molestias",
    "horario de interrupciones",
)

_MANTENIMIENTO_TITLE_MARKERS: tuple[str, ...] = (
    "mantenimiento",
    "interrupcion",
)

_WAF_BODY_MARKERS: tuple[str, ...] = (
    "request blocked",
    "your request was blocked",
    "web application firewall",
    "waf",
    "reference id",
    "support id",
)

_WAF_CORRELATION_MARKERS: tuple[str, ...] = (
    "reference id",
    "support id",
)


def _utcnow() -> datetime:
    """Return the current UTC timestamp.

    Delegates to :func:`core.time.clock.now` so call-sites remain
    uniform across the production codebase.
    """
    return now()


def _parse_http_date_retry_after(
    value: str,
    *,
    now: datetime | None,
) -> int | None:
    """Return the clamped delta-seconds for an HTTP-date ``Retry-After``.

    Attempts to parse ``value`` as an RFC 9110 HTTP-date via
    :func:`email.utils.parsedate_to_datetime`, then returns the
    integer seconds between ``now`` (UTC) and the parsed instant,
    clamped to a minimum of zero. Returns ``None`` when ``value`` is
    not a recognisable HTTP-date.
    """
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    parsed = coerce_utc_aware(parsed)
    reference = coerce_utc_aware(now) if now is not None else datetime.now(tz=UTC)
    delta = int((parsed - reference).total_seconds())
    return max(delta, 0)


def _bounded_fragment(html: str) -> str:
    """Return the first ``_MAX_FRAGMENT_CHARS`` of ``html``.

    Args:
        html: The raw response body captured by the caller.

    Returns:
        At most 4096 characters of the input, preserving ordering so
        downstream log readers see a recognisable prefix.
    """
    if len(html) <= _MAX_FRAGMENT_CHARS:
        return html
    return html[:_MAX_FRAGMENT_CHARS]


def _normalise_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return a case-insensitive, lowercase-keyed copy of ``headers``."""
    return {key.lower(): value for key, value in headers.items()}


def _extract_title(html: str, lowered: str | None = None) -> str:
    """Return the first ``<title>...</title>`` value, lowercased.

    A tiny parser deliberately avoids pulling in an HTML library just
    for the title lookup. Returns an empty string if no title tag is
    present. When the caller has already lowercased the body they may
    pass it via ``lowered`` to avoid a redundant allocation.
    """
    lowered = lowered if lowered is not None else html.lower()
    start = lowered.find("<title")
    if start == -1:
        return ""
    gt = lowered.find(">", start)
    if gt == -1:
        return ""
    end = lowered.find("</title>", gt)
    if end == -1:
        return ""
    return lowered[gt + 1 : end].strip()


def _body_outside_title(lowered: str) -> str:
    """Return the lowercased document with its first ``<title>`` element removed.

    The title is counted as its own kind of evidence and must not also count
    as body evidence. Scanning the whole document for body markers made the
    literal ``mantenimiento`` inside ``<title>mantenimiento</title>`` score
    once as a body hit and once as a title hit, which is exactly the
    two-source agreement the corroboration rule exists to require — so a
    title-only page satisfied a guard written to reject it.

    Only the FIRST title element is removed, matching what
    :func:`_extract_title` reads as the document title. A later ``<title>``
    inside an inline SVG is ordinary body content and is left to be scanned as
    such.
    """
    start = lowered.find("<title")
    if start == -1:
        return lowered
    gt = lowered.find(">", start)
    if gt == -1:
        return lowered
    end = lowered.find("</title>", gt)
    if end == -1:
        return lowered
    return lowered[:start] + lowered[end + len("</title>") :]


def _matches_mantenimiento(lowered_body: str, title: str) -> tuple[str, ...]:
    """Return the ordered tuple of mantenimiento markers detected.

    Args:
        lowered_body: The response body pre-lowercased.
        title: The lowercased ``<title>`` contents, if any.

    Returns:
        A frozen tuple of the markers that matched. Empty when no
        marker fires.
    """
    outside_title = _body_outside_title(lowered_body)
    hits: list[str] = []
    for marker in _MANTENIMIENTO_MARKERS:
        if marker in outside_title:
            hits.append(marker)
    title_hits: list[str] = []
    for marker in _MANTENIMIENTO_TITLE_MARKERS:
        if title and marker in title:
            title_hits.append(f"title:{marker}")
    return tuple(hits + title_hits)


def parse_mantenimiento_banner(
    url: str,
    http_status: int,
    headers: Mapping[str, str],
    html: str,
    *,
    rate_limit_retry_after_default: int,
    _lowered: str | None = None,
) -> SiteHealthStatus | None:
    """Detect an AEAT maintenance banner or interstitial.

    Classifies the response as :attr:`SiteHealthState.MANTENIMIENTO`
    when two or more curated body markers match, or when exactly one
    body marker matches alongside a title containing ``mantenimiento``
    or ``interrupcion``. A title-only match with zero body markers
    **never** classifies: at least one body-marker hit is required as
    corroborating evidence to suppress false positives from
    unrelated pages whose ``<title>`` happens to mention maintenance.

    Args:
        url: The probe URL.
        http_status: The observed HTTP status code.
        headers: Case-insensitive mapping of response headers.
        html: The response body.
        rate_limit_retry_after_default: Ignored here; accepted so the
            three parsers share a uniform signature wired from the
            browser session hook.
        _lowered: Optional pre-lowercased body forwarded from
            :func:`evaluate_response` to avoid redundant work. Public
            callers should leave it ``None``.

    Returns:
        A populated :class:`SiteHealthStatus` or ``None`` when no
        maintenance markers fire.
    """
    del headers, rate_limit_retry_after_default
    lowered = _lowered if _lowered is not None else html.lower()
    title = _extract_title(html, lowered)
    hits = _matches_mantenimiento(lowered, title)
    if not hits:
        return None
    title_hit_count = sum(1 for h in hits if h.startswith("title:"))
    body_hit_count = len(hits) - title_hit_count
    if body_hit_count == 0:
        return None
    if body_hit_count < 2 and title_hit_count == 0:
        return None
    return SiteHealthStatus(
        state=SiteHealthState.MANTENIMIENTO,
        evidence=SiteHealthEvidence(
            url=parse_site_health_url(url),
            http_status=http_status,
            html_fragment=_bounded_fragment(html),
            detected_markers=hits,
        ),
        observed_at=_utcnow(),
    )


def parse_waf_challenge(
    url: str,
    http_status: int,
    headers: Mapping[str, str],
    html: str,
    *,
    rate_limit_retry_after_default: int,
    _lowered: str | None = None,
) -> SiteHealthStatus | None:
    """Detect a WAF block / challenge page.

    Triggers either when the response is a 403 and any WAF marker is
    present, or when the body contains ``request blocked`` alongside
    a ``reference id`` / ``support id`` correlation token regardless
    of status code.

    Args:
        url: The probe URL.
        http_status: The observed HTTP status code.
        headers: Case-insensitive mapping of response headers.
        html: The response body.
        rate_limit_retry_after_default: Ignored; reserved for interface parity.
        _lowered: Pre-computed lowercased ``html``; computed from ``html`` when omitted.

    Returns:
        A populated :class:`SiteHealthStatus` or ``None`` when the
        response does not look WAF-blocked.
    """
    del headers, rate_limit_retry_after_default
    lowered = _lowered if _lowered is not None else html.lower()
    body_hits = tuple(marker for marker in _WAF_BODY_MARKERS if marker in lowered)
    if not body_hits:
        return None
    has_correlation = any(marker in lowered for marker in _WAF_CORRELATION_MARKERS)
    is_403 = http_status == 403
    blocked_phrase_present = "request blocked" in lowered
    if not (is_403 or (blocked_phrase_present and has_correlation)):
        return None
    return SiteHealthStatus(
        state=SiteHealthState.WAF_CHALLENGE,
        evidence=SiteHealthEvidence(
            url=parse_site_health_url(url),
            http_status=http_status,
            html_fragment=_bounded_fragment(html),
            detected_markers=body_hits,
        ),
        observed_at=_utcnow(),
    )


def parse_rate_limit_response(
    url: str,
    http_status: int,
    headers: Mapping[str, str],
    html: str,
    *,
    rate_limit_retry_after_default: int,
    now: datetime | None = None,
    _lowered: str | None = None,
) -> SiteHealthStatus | None:
    """Detect a rate-limit response (HTTP 429 or 503).

    Short-circuits unless ``http_status`` is 429 or 503. When the
    response is a 503 and the body also matches a maintenance marker
    the parser yields ``None`` so :func:`parse_mantenimiento_banner`
    can win; AEAT mantenimiento pages frequently answer with 503.

    ``Retry-After`` is read case-insensitively from ``headers`` and
    supports both forms permitted by RFC 9110 §10.2.3: a non-negative
    integer delta-seconds, or an HTTP-date. For HTTP-date values the
    delta is computed against ``now`` (defaulting to
    :func:`datetime.now` in UTC), clamped to a non-negative integer.
    If both parses fail, or the computed delta would be zero, the
    parser falls back to ``rate_limit_retry_after_default``.

    Args:
        url: The probe URL.
        http_status: The observed HTTP status code.
        headers: Case-insensitive mapping of response headers.
        html: The response body.
        rate_limit_retry_after_default: Fallback value (seconds) when
            the ``Retry-After`` header is missing or unparseable.
        now: Injection seam for deterministic tests of the HTTP-date
            branch. Defaults to :func:`datetime.now` in UTC at call
            time.
        _lowered: Optional pre-lowercased body forwarded from
            :func:`evaluate_response`.

    Returns:
        A populated :class:`SiteHealthStatus` or ``None`` when the
        response is not a rate-limit answer.
    """
    if http_status not in {429, 503}:
        return None
    lowered = _lowered if _lowered is not None else html.lower()
    if http_status == 503:
        title = _extract_title(html, lowered)
        if _matches_mantenimiento(lowered, title):
            return None
    normalised = _normalise_headers(headers)
    raw_retry_after = normalised.get("retry-after")
    retry_after: int = rate_limit_retry_after_default
    marker_value: str
    if raw_retry_after is not None:
        stripped = raw_retry_after.strip()
        try:
            parsed = int(stripped)
        except ValueError:
            parsed_seconds = _parse_http_date_retry_after(stripped, now=now)
            if parsed_seconds is None:
                marker_value = f"retry-after:invalid:{raw_retry_after[:32]}"
            elif parsed_seconds >= 1:
                retry_after = parsed_seconds
                marker_value = f"retry-after:http-date:{parsed_seconds}"
            else:
                marker_value = f"retry-after:http-date-non-positive:{parsed_seconds}"
        else:
            if parsed >= 1:
                retry_after = parsed
                marker_value = f"retry-after:{parsed}"
            else:
                marker_value = f"retry-after:non-positive:{parsed}"
    else:
        marker_value = f"retry-after:default:{rate_limit_retry_after_default}"
    return SiteHealthStatus(
        state=SiteHealthState.RATE_LIMITED,
        evidence=SiteHealthEvidence(
            url=parse_site_health_url(url),
            http_status=http_status,
            html_fragment=_bounded_fragment(html),
            detected_markers=(marker_value,),
        ),
        observed_at=_utcnow(),
        retry_after_seconds=retry_after,
    )


def evaluate_response(
    url: str,
    http_status: int,
    headers: Mapping[str, str],
    html: str,
    *,
    rate_limit_retry_after_default: int,
) -> SiteHealthStatus | None:
    """Run the full parser suite and return the first non-OK hit.

    This is the public parser entry point consumed by
    :func:`adapters.outbound.aeat.browser._site_health_probe.probe_response`.
    :class:`~adapters.outbound.aeat.browser.BrowserSession` then raises
    :class:`core.errors.SiteHealthError` for any returned status.

    Parsers are evaluated in cost-then-specificity order:

    1. :func:`parse_rate_limit_response` (cheapest, header-first
       short-circuit; yields to mantenimiento when a 503 carries
       mantenimiento markers).
    2. :func:`parse_mantenimiento_banner`.
    3. :func:`parse_waf_challenge`.

    Args:
        url: The probe URL.
        http_status: The observed HTTP status code.
        headers: Case-insensitive mapping of response headers.
        html: The response body.
        rate_limit_retry_after_default: Fallback ``Retry-After`` value
            in seconds, forwarded to the rate-limit parser.

    Returns:
        A populated :class:`SiteHealthStatus` describing the detected
        non-OK state, or ``None`` when no parser classified the
        response (i.e. the response looks healthy).
    """
    lowered = html.lower()
    for parser in (
        parse_rate_limit_response,
        parse_mantenimiento_banner,
        parse_waf_challenge,
    ):
        result = parser(
            url,
            http_status,
            headers,
            html,
            rate_limit_retry_after_default=rate_limit_retry_after_default,
            _lowered=lowered,
        )
        if result is not None:
            return result
    return None
