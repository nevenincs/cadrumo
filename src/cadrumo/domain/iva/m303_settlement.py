"""LIVA annual-settlement timing for Modelo 303 regularisation flows."""

from __future__ import annotations

from datetime import date, datetime

from ...core.modelo import Modelo
from ...core.period import Period, PeriodKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import governed_facts_in_scope

# fact-relocation: M303 annual settlement ordering is resolved through the
# generation-pinned revision directory; the authored revision remains external.


def _m303_annual_settlement_period_tokens(
    *,
    filing_year: int | None = None,
    authority: PinnedAuthorityOperation | None = None,
) -> tuple[str, ...]:
    """Read annual-settlement tokens from the selected M303 period surface."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError(
            "Modelo 303 settlement ordering requires an explicit pinned authority operation or scope",
        )
    year = filing_year or date.today().year
    revision_for_context = getattr(selected_authority, "revision_for_context", None)
    if revision_for_context is None:
        raise RegistryValidationError(
            "Modelo 303 settlement ordering requires a generation-pinned authority operation",
        )
    revision = revision_for_context(
        str(Modelo("303")),
        filing_year=year,
        period="0A",
        on=date(year, 12, 31),
    )
    declared = tuple(Period.from_year_and_code(year, token) for token in revision.period_selector.declared_periods)
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


def m303_annual_settlement_period_order(
    period: Period,
    *,
    authority: PinnedAuthorityOperation | None = None,
) -> int | None:
    """Return the legal annual-settlement order for one Modelo 303 period.

    The selected registry revision identifies the terminal quarterly period and
    the annual-only period for LIVA annual regularisations. Midyear periods
    have no settlement order.
    """
    tokens = _m303_annual_settlement_period_tokens(
        filing_year=period.filing_year,
        authority=authority,
    )
    try:
        return tokens.index(period.registry_token)
    except ValueError:
        return None


def is_m303_annual_settlement_period(
    period: Period,
    *,
    authority: PinnedAuthorityOperation | None = None,
) -> bool:
    """Return whether the typed period is a legal Modelo 303 annual settlement."""
    return m303_annual_settlement_period_order(period, authority=authority) is not None


def m303_annual_settlement_order_key(
    period: Period,
    captured_at: datetime,
    *,
    authority: PinnedAuthorityOperation | None = None,
) -> tuple[int, datetime] | None:
    """Return the legal settlement precedence key for an observed source period.

    The annual-only settlement form wins after the terminal quarterly period,
    then the later capture wins within the same form. Non-settlement periods
    have no key and must not participate in annual carry selection.
    """
    order = m303_annual_settlement_period_order(period, authority=authority)
    return None if order is None else (order, captured_at)


def m303_annual_settlement_period_tokens(*, authority: PinnedAuthorityOperation | None = None) -> tuple[str, ...]:
    """Return legal Modelo 303 settlement tokens in increasing settlement order."""
    return _m303_annual_settlement_period_tokens(authority=authority)


__all__ = [
    "is_m303_annual_settlement_period",
    "m303_annual_settlement_order_key",
    "m303_annual_settlement_period_order",
    "m303_annual_settlement_period_tokens",
]
