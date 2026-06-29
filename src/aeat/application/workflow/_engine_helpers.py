"""Private helpers for workflow-engine formatting and deadline metadata."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from ...core import Period

CertificateSeverityValue = Literal["OK", "WARN", "CRITICAL", "EXPIRED"]


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
    """Resolve a :class:`~aeat.core.Period` to ``(filing_year, registry_period)``."""
    return period.year, period.registry_token


def registry_filing_year(period: Period) -> int:
    """Return the filing year from a typed :class:`~aeat.core.Period`."""
    return period.year


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


def draft_blocking_finding_descriptions(draft: object) -> tuple[str, ...]:
    """Summarise the ERROR/WARNING findings that keep a built draft out of the ready state.

    The ``BUILDING_DRAFT`` gate aborts with ``DRAFT_HAS_ERRORS`` whenever the
    builder hands back a draft still below ``LISTO_PARA_PRESENTAR``. Without the
    underlying findings the abort is opaque (operators see only
    ``status=BORRADOR``), so this projects each blocking finding to a compact
    ``severity:code (casilla)`` description the abort step can surface.
    """
    findings = getattr(draft, "findings", ()) or ()
    descriptions: list[str] = []
    for finding in findings:
        severity = enum_value(getattr(finding, "severity", None))
        if severity not in {"error", "warning"}:
            continue
        code = enum_value(getattr(finding, "code", None)) or "unknown"
        casilla = enum_value(getattr(finding, "casilla_id", None))
        descriptions.append(f"{severity}:{code}" + (f" ({casilla})" if casilla else ""))
    return tuple(descriptions)


__all__ = [
    "DeadlineRole",
    "FilingWindowState",
    "classify_cert_expiry",
    "draft_blocking_finding_descriptions",
    "enum_value",
    "registry_filing_year",
    "registry_period_token",
    "summary_text",
]
