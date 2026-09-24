"""LIVA annual-settlement timing for Modelo 303 regularisation flows."""

from __future__ import annotations

from datetime import datetime

from ...core.modelo import Modelo
from ...core.period import Period, PeriodKind
from ..calculations.registry.authority import PinnedAuthorityOperation
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.governed_fact_scope import governed_facts_in_scope

# Registry authority: M303 annual settlement ordering is resolved through the
# generation-pinned revision directory; the authored revision remains external.

_M303_LIQUIDATION_KINDS: frozenset[PeriodKind] = frozenset((PeriodKind.QUARTERLY, PeriodKind.MONTHLY))


def _terminal_settlement_token(
    period: Period,
    *,
    authority: PinnedAuthorityOperation | None,
) -> str:
    """Return the last declared liquidation period of the period's year and cadence.

    Modelo 303 liquidation periods are calendar quarters or, for monthly filers,
    calendar months (RD 1624/1992 art. 71.3); an annual token such as ``0A``
    belongs to Modelo 390 and refuses. The requested period is resolved through
    the canonical revision selector at its own end date, so an undeclared token
    refuses instead of silently becoming a non-settlement period. The terminal
    candidate is read across every revision declaring periods for the year,
    because a same-year design split declares early and late periods in
    different revisions, and is then itself resolved for the requested year.

    Raises:
        RegistryValidationError: When the period is not a quarterly or monthly
            liquidation period, or no generation-pinned authority is in scope.
        NoRevisionForPeriodError: When no Modelo 303 revision declares the
            requested period or its derived terminal period for the year.
    """
    if not period.has_date_span() or period.kind not in _M303_LIQUIDATION_KINDS:
        raise RegistryValidationError(
            f"Modelo 303 settlement ordering requires a quarterly or monthly liquidation period; got {period}",
        )
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError(
            "Modelo 303 settlement ordering requires an explicit pinned authority operation or scope",
        )
    revision_for_context = getattr(selected_authority, "revision_for_context", None)
    modelo_directory = getattr(selected_authority, "modelo_directory", None)
    if revision_for_context is None or modelo_directory is None:
        raise RegistryValidationError(
            "Modelo 303 settlement ordering requires a generation-pinned authority operation",
        )
    modelo = str(Modelo("303"))
    year = period.filing_year
    revision_for_context(modelo, filing_year=year, period=period.registry_token, on=period.end_date)
    same_cadence = tuple(
        candidate
        for revision in modelo_directory(modelo).revisions
        for token in revision.period_selector.periods_for_year(year)
        if (candidate := Period.from_year_and_code(year, str(token))).kind is period.kind
    )
    if not same_cadence:
        raise RegistryValidationError(
            f"Modelo 303 declares no {period.kind.value} liquidation periods for {year}",
        )
    terminal = max(same_cadence, key=lambda candidate: candidate.end_date)
    if terminal.registry_token != period.registry_token:
        revision_for_context(modelo, filing_year=year, period=terminal.registry_token, on=terminal.end_date)
    return terminal.registry_token


def m303_annual_settlement_period_order(
    period: Period,
    *,
    authority: PinnedAuthorityOperation | None = None,
) -> int | None:
    """Return the legal annual-settlement order for one Modelo 303 period.

    The annual prorrata and capital-goods regularisations belong to the last
    liquidation of the calendar year (LIVA arts. 105 and 110). That is the final
    declared quarter for quarterly filers and the final declared month for
    monthly filers (RD 1624/1992 art. 71.3). Earlier periods have no order.

    Raises:
        RegistryValidationError: When the period is not a Modelo 303
            quarterly or monthly liquidation period.
        NoRevisionForPeriodError: When no Modelo 303 revision declares the period.
    """
    terminal = _terminal_settlement_token(period, authority=authority)
    return 0 if terminal == period.registry_token else None


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

    Within the settlement form the later capture wins. Non-settlement periods
    have no key and must not participate in annual carry selection.
    """
    order = m303_annual_settlement_period_order(period, authority=authority)
    return None if order is None else (order, captured_at)


__all__ = [
    "is_m303_annual_settlement_period",
    "m303_annual_settlement_order_key",
    "m303_annual_settlement_period_order",
]
