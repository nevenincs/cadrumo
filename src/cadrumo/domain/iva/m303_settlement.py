"""LIVA annual-settlement timing for Modelo 303 regularisation flows."""

from __future__ import annotations

from datetime import datetime

from ...core.modelo import Modelo
from ...core.period import Period, PeriodKind
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.queries import RegistryQueryService

# fact-relocation: M303 annual settlement ordering is resolved through RegistryQueryService; authored revision remains external.


def _m303_annual_settlement_period_tokens(
    *,
    filing_year: int | None = None,
) -> tuple[str, ...]:
    """Read annual-settlement tokens from the selected M303 period surface."""
    report = RegistryQueryService(bundled_authority()).describe_modelo(
        str(Modelo("3")),
    )
    year = filing_year or report.filing_year or report.valid_from.year
    declared = tuple(Period.from_year_and_code(year, token) for token in report.periods)
    annual = {candidate.registry_token for candidate in declared if candidate.kind is PeriodKind.ANNUAL}
    quarterly = tuple(candidate for candidate in declared if candidate.is_quarterly)
    if not quarterly:
        return ()
    final_quarter = max(
        quarterly,
        key=lambda candidate: candidate.quarter_ordinal if candidate.quarter_ordinal is not None else -1,
    )
    return tuple(
        candidate.registry_token
        for candidate in declared
        if candidate.registry_token in annual or candidate.registry_token == final_quarter.registry_token
    )


def m303_annual_settlement_period_order(period: Period) -> int | None:
    """Return the legal annual-settlement order for one Modelo 303 period.

    The selected registry revision identifies the terminal quarterly period and
    the annual-only period for LIVA annual regularisations. Midyear periods
    have no settlement order.
    """
    tokens = _m303_annual_settlement_period_tokens(
        filing_year=period.filing_year,
    )
    try:
        return tokens.index(period.registry_token)
    except ValueError:
        return None


def is_m303_annual_settlement_period(period: Period) -> bool:
    """Return whether the typed period is a legal Modelo 303 annual settlement."""
    return m303_annual_settlement_period_order(period) is not None


def m303_annual_settlement_order_key(period: Period, captured_at: datetime) -> tuple[int, datetime] | None:
    """Return the legal settlement precedence key for an observed source period.

    The annual-only settlement form wins after the terminal quarterly period,
    then the later capture wins within the same form. Non-settlement periods
    have no key and must not participate in annual carry selection.
    """
    order = m303_annual_settlement_period_order(period)
    return None if order is None else (order, captured_at)


def m303_annual_settlement_period_tokens() -> tuple[str, ...]:
    """Return legal Modelo 303 settlement tokens in increasing settlement order."""
    return _m303_annual_settlement_period_tokens()


__all__ = [
    "is_m303_annual_settlement_period",
    "m303_annual_settlement_order_key",
    "m303_annual_settlement_period_order",
    "m303_annual_settlement_period_tokens",
]
