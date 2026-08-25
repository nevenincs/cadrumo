"""Canonical workflow-engine deadline and certificate metadata contracts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from ...core import Period

type CertificateSeverityValue = Literal["OK", "WARN", "CRITICAL", "EXPIRED"]


class DeadlineRole(StrEnum):
    """Role of a deadline within workflow step metadata."""

    INFORMATIONAL = "informational"
    BINDING = "binding"


class FilingWindowState(StrEnum):
    """State of the filing window for a given (modelo, period) at workflow time."""

    ABSENT = "absent"
    FUTURE = "future"
    OPEN = "open"
    CLOSED = "closed"


def registry_period_token(period: Period) -> tuple[int, str]:
    """Resolve a :class:`~core.Period` to ``(filing_year, registry_period)``."""
    return period.filing_year, period.registry_token


def registry_filing_year(period: Period) -> int:
    """Return the filing year from a typed :class:`~core.Period`."""
    return period.filing_year


def classify_cert_expiry(
    *,
    not_after: date,
    today: date,
    warn_days: int,
    critical_days: int,
) -> tuple[CertificateSeverityValue, int]:
    """Classify a certificate's expiry window against operator thresholds."""
    days_until_expiry = (not_after - today).days
    if days_until_expiry <= 0:
        return ("EXPIRED", days_until_expiry)
    if days_until_expiry <= critical_days:
        return ("CRITICAL", days_until_expiry)
    if days_until_expiry <= warn_days:
        return ("WARN", days_until_expiry)
    return ("OK", days_until_expiry)


__all__ = [
    "CertificateSeverityValue",
    "DeadlineRole",
    "FilingWindowState",
    "classify_cert_expiry",
    "registry_filing_year",
    "registry_period_token",
]
