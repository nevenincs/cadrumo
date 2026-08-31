"""Private health-probe helper for :class:`adapters.outbound.aeat.browser.BrowserSession`.

The session navigation hook calls this helper after every ``page.goto`` and
before raising :class:`core.errors.SiteHealthError` for non-OK
classifications. Keeping the helper isolated makes the forbidden-import guard
trivial: this module MUST NOT import anything from
:mod:`adapters.outbound.aeat.auth`, :mod:`application.filing`, or
:mod:`domain.transactions`.

See Also:
    :func:`adapters.outbound.aeat.browser._site_health_parsers.evaluate_response`
        Pure parser suite delegated to by :func:`probe_response`.
    :class:`adapters.outbound.aeat.browser.site_health_records.SiteHealthStatus`
        Concrete status record returned for maintenance, WAF, rate-limit, and
        unreachable classifications.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._site_health_parsers import evaluate_response
from .site_health_records import SiteHealthStatus


def probe_response(
    url: str,
    http_status: int,
    headers: Mapping[str, str],
    html: str,
    *,
    rate_limit_retry_after_default: int,
) -> SiteHealthStatus | None:
    """Classify a response via the parser suite.

    This is the narrow boundary between Playwright navigation and the pure
    parser code. It keeps :class:`~adapters.outbound.aeat.browser.BrowserSession`
    dependent on one function while preserving the parser module's lack of
    browser, auth, filing, or transaction imports.

    Args:
        url: The probe URL whose response is being classified.
        http_status: The HTTP status code observed on the response.
        headers: Case-insensitive mapping of response headers.
        html: The response body.
        rate_limit_retry_after_default: Fallback ``Retry-After`` value
            used by the rate-limit parser when no header is present.

    Returns:
        A :class:`SiteHealthStatus` describing the detected non-OK
        state, or ``None`` when the response looks healthy.
    """
    return evaluate_response(
        url,
        http_status,
        headers,
        html,
        rate_limit_retry_after_default=rate_limit_retry_after_default,
    )
