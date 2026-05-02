"""Private health-probe helper for :class:`aeat.adapters.outbound.aeat.browser.BrowserSession`.

The session navigation hook calls this helper after every ``page.goto``.
Keeping this helper isolated in its own module makes the forbidden-import
guard trivial: this module MUST NOT import anything from
:mod:`aeat.adapters.outbound.aeat.auth`, :mod:`aeat.application.filing`, or
:mod:`aeat.domain.transactions`.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._site_health import SiteHealthStatus
from ._site_health_parsers import evaluate_response


def probe_response(
    url: str,
    http_status: int,
    headers: Mapping[str, str],
    html: str,
    *,
    rate_limit_retry_after_default: int,
) -> SiteHealthStatus | None:
    """Classify a response via the parser suite.

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
