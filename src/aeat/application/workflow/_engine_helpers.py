"""Private helpers for workflow-engine formatting and deadline metadata."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from ...domain.period import PeriodValidationError, parse_canonical_period
from ._errors import WorkflowError

CertificateSeverityValue = Literal["OK", "WARN", "CRITICAL", "EXPIRED"]


class DeadlineRole(StrEnum):
    """Role of a deadline within workflow step metadata."""

    INFORMATIONAL = "informational"
    BINDING = "binding"


class FilingWindowState(StrEnum):
    """State of the filing window for a given (modelo, period) at workflow time."""

    ABSENT = "absent"
    OPEN = "open"
    CLOSED = "closed"


def registry_period_token(period: str) -> tuple[int, str]:
    """Resolve a deadline-engine period token to ``(filing_year, registry_period)``."""
    try:
        return parse_canonical_period(period)
    except PeriodValidationError as exc:
        raise WorkflowError(
            translated_message="application.workflow.errors.period_registry_unmappable",
            context={"period": period},
        ) from exc


def registry_filing_year(period: str) -> int:
    """Resolve the filing year from a workflow period token."""
    try:
        filing_year, _registry_period = parse_canonical_period(period)
    except PeriodValidationError as exc:
        raise WorkflowError(
            translated_message="application.workflow.errors.period_registry_year_unresolvable",
            context={"period": period},
        ) from exc
    return filing_year


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


def summary_text(en: str) -> str:
    """Build a workflow summary string."""
    return en


def enum_value(value: object) -> str:
    """Return ``Enum.value`` when present, otherwise ``str(value)``."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw)


__all__ = [
    "DeadlineRole",
    "FilingWindowState",
    "classify_cert_expiry",
    "enum_value",
    "registry_filing_year",
    "registry_period_token",
    "summary_text",
]
