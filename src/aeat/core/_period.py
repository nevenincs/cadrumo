"""Canonical period code enumeration for filing periods.

Period codes represent the filing frequency and scheme for tax returns:
- Quarterly: 1T, 2T, 3T, 4T (standard filing periods)
- Instalment: 1P, 2P, 3P, 4P (corporate-tax/IS instalment periods)
- Annual: 0A
- Monthly: 01-12 (calendar months)
- OSS/IOSS: EXT-1T, EXT-2T, EXT-3T, EXT-4T (extra-Union scheme)
- Ad-hoc/Event: AD-HOC, EVENT-N (event-driven filings)

StandardPeriodCode is the canonical StrEnum for the basic period codes
(1T-4T, 1P-4P, 0A, 01-12). Extended forms (EXT-*, AD-HOC, EVENT-*) are
validated via separate regex patterns for modeller flexibility.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator


class StandardPeriodCode(StrEnum):
    """Canonical enumeration of standard filing-period codes."""

    Q1 = "1T"
    Q2 = "2T"
    Q3 = "3T"
    Q4 = "4T"

    P1 = "1P"
    P2 = "2P"
    P3 = "3P"
    P4 = "4P"

    ANNUAL = "0A"

    JAN = "01"
    FEB = "02"
    MAR = "03"
    APR = "04"
    MAY = "05"
    JUN = "06"
    JUL = "07"
    AUG = "08"
    SEP = "09"
    OCT = "10"
    NOV = "11"
    DEC = "12"


_STANDARD_PERIOD_SET = frozenset(StandardPeriodCode)
_EXTENDED_PERIOD_SET = frozenset(("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T"))
_AD_HOC_PERIOD = "AD-HOC"
_EXT_PERIOD_RE = re.compile(r"^EXT-[1-4]T$")
_EVENT_PERIOD_RE = re.compile(r"^EVENT-\d+$")


def _validate_period_against_registry(value: str) -> str:
    """Validate and normalize a period code against the union of accepted forms.

    Accepts StandardPeriodCode members, extended OSS/IOSS forms (EXT-1T..EXT-4T),
    ad-hoc literal (AD-HOC), and event-driven forms (EVENT-N where N is an integer).

    Raises ValueError with the full accepted-set list on rejection; pydantic
    wraps it into a ValidationError at the BeforeValidator boundary.
    """
    if not isinstance(value, str):
        raise ValueError(f"period code must be a string, got {type(value).__name__}")

    normalized = value.strip().upper()

    if normalized in _STANDARD_PERIOD_SET:
        return normalized
    if normalized in _EXTENDED_PERIOD_SET:
        return normalized
    if normalized == _AD_HOC_PERIOD:
        return normalized
    if _EVENT_PERIOD_RE.match(normalized):
        return normalized

    accepted = _format_accepted_period_set()
    raise ValueError(
        f"invalid period code '{value}'; accepted forms: {accepted}"
    )


def accepted_period_codes() -> tuple[str, ...]:
    """Return the fully enumerable period codes (StandardPeriodCode + extended literals)."""
    return tuple(sorted(_STANDARD_PERIOD_SET | _EXTENDED_PERIOD_SET | {_AD_HOC_PERIOD}))


def accepted_period_patterns() -> tuple[str, ...]:
    """Return the period code patterns (including regex shapes for EVENT-N)."""
    return (
        "StandardPeriodCode (1T-4T, 1P-4P, 0A, 01-12)",
        "Extended OSS/IOSS (EXT-1T, EXT-2T, EXT-3T, EXT-4T)",
        "Ad-hoc (AD-HOC)",
        "Event-driven (EVENT-N where N is an integer)",
    )


def _format_accepted_period_set() -> str:
    """Format the accepted period set for error messages."""
    standard = sorted(_STANDARD_PERIOD_SET)
    extended = sorted(_EXTENDED_PERIOD_SET)
    lines = [
        f"StandardPeriodCode: {', '.join(standard)}",
        f"Extended: {', '.join(extended)}",
        f"Ad-hoc: {_AD_HOC_PERIOD}",
        f"Event-driven: EVENT-N (where N is an integer)",
    ]
    return "; ".join(lines)


RegistryPeriodCode = Annotated[str, BeforeValidator(_validate_period_against_registry)]

__all__ = [
    "StandardPeriodCode",
    "RegistryPeriodCode",
    "accepted_period_codes",
    "accepted_period_patterns",
]
