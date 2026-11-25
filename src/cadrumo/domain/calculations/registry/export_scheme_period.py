"""The value a design's period row prints, read from the period being filed."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ....core.period import Period, PeriodKind
from .schema_exports import ExportFieldDefinition


def scheme_period_value(field: ExportFieldDefinition, period: Period) -> object | None:
    """Project the filed period into the part this row prints, or ``None`` when it prints none.

    A period whose cadence differs from the row's ordinal also answers ``None``,
    so such a row keeps its ordinary required-value refusal.
    """
    match field.scheme_period_part:
        case None:
            return None
        case "filing_year":
            return period.filing_year
        case "period_type":
            return field.scheme_period_type
        case "quarter_ordinal":
            return period.scheme_quarter_ordinal or period.quarter_ordinal
        case "month_ordinal":
            return period.end_date.month if period.kind is PeriodKind.MONTHLY else None


def contradicts_scheme_period(field: ExportFieldDefinition, period: Period, entered: object) -> bool:
    """Say whether an operator-entered value disagrees with the part the period prints.

    An absent or blank entry contradicts nothing, because the period supplies the row.
    """
    expected = scheme_period_value(field, period)
    if expected is None or entered is None or not str(entered).strip():
        return False
    return not _same_printed_value(str(entered).strip(), str(expected))


def _same_printed_value(entered: str, expected: str) -> bool:
    try:
        return Decimal(entered) == Decimal(expected)
    except InvalidOperation:
        return entered == expected


__all__ = ["contradicts_scheme_period", "scheme_period_value"]
