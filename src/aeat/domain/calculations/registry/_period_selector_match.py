"""Period-selector matching helpers for registry revision selection."""

from __future__ import annotations

import re
from collections.abc import Iterable

_EVENT_SELECTOR_PERIOD = "EVENT-N"
_EVENT_PERIOD_RE = re.compile(r"^EVENT-\d+$", re.I)


def selector_period_matches_request(selector_period: str, requested_period: str) -> bool:
    """Return whether one selector token covers an operator/request token."""
    selector = selector_period.strip()
    requested = requested_period.strip()
    if selector.upper() == _EVENT_SELECTOR_PERIOD:
        requested_upper = requested.upper()
        return requested_upper == _EVENT_SELECTOR_PERIOD or _EVENT_PERIOD_RE.fullmatch(requested_upper) is not None
    return selector.casefold() == requested.casefold()


def selector_token_for_request(selector_periods: Iterable[str], requested_period: str) -> str | None:
    """Return the declared selector token matching a requested period, if any."""
    for selector_period in selector_periods:
        if selector_period_matches_request(selector_period, requested_period):
            return selector_period
    return None


def registry_period_for_request(selector_periods: Iterable[str], requested_period: str) -> str | None:
    """Return the concrete registry period to use for a requested scope."""
    selector_period = selector_token_for_request(selector_periods, requested_period)
    if selector_period is None:
        return None
    if selector_period.upper() != _EVENT_SELECTOR_PERIOD:
        return selector_period
    requested_upper = requested_period.strip().upper()
    if requested_upper == _EVENT_SELECTOR_PERIOD:
        return selector_period
    return requested_upper


__all__ = [
    "registry_period_for_request",
    "selector_period_matches_request",
    "selector_token_for_request",
]
