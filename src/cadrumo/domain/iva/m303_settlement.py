"""LIVA annual-settlement timing for Modelo 303 regularisation flows."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ...core.modelo import Modelo
from ...core.period import Period, PeriodKind
from ..calculations.registry.authority import PinnedAuthorityOperation
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.governed_fact_scope import governed_facts_in_scope

if TYPE_CHECKING:
    from ..calculations.registry.temporal import RevisionSelectionMetadata

# Registry authority: M303 annual settlement ordering is resolved through the
# generation-pinned revision directory; the authored revision remains external.

_M303_LIQUIDATION_KINDS: frozenset[PeriodKind] = frozenset((PeriodKind.QUARTERLY, PeriodKind.MONTHLY))


def _pinned_selection(authority: PinnedAuthorityOperation | None) -> tuple[Any, Any]:
    """Return the pinned revision selector and directory reader, or refuse."""
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
    return revision_for_context, modelo_directory


def m303_cadence_liquidation_periods(
    filing_year: int,
    kind: PeriodKind,
    *,
    authority: PinnedAuthorityOperation | None = None,
) -> tuple[Period, ...]:
    """Return every Modelo 303 liquidation period one cadence declares for a year.

    The periods are read from the period selector of every revision declaring
    periods for the year, because a same-year design split declares early and
    late periods in different revisions, and are returned in calendar order. A
    cadence the registry declares no period for yields an empty tuple, so a
    caller that does not know the filer's cadence (the annual summary) can ask
    for each one.

    Raises:
        RegistryValidationError: When ``kind`` is not a Modelo 303 liquidation
            cadence, or no generation-pinned authority is in scope.
    """
    if kind not in _M303_LIQUIDATION_KINDS:
        raise RegistryValidationError(
            f"Modelo 303 liquidation periods are quarterly or monthly; got {kind.value}",
        )
    _revision_for_context, modelo_directory = _pinned_selection(authority)
    same_cadence = _same_cadence_periods(
        modelo_directory(str(Modelo("303"))).revisions,
        year=filing_year,
        kind=kind,
    )
    return tuple(sorted(dict.fromkeys(same_cadence), key=lambda candidate: candidate.end_date))


def m303_liquidation_periods(
    period: Period,
    *,
    authority: PinnedAuthorityOperation | None = None,
) -> tuple[Period, ...]:
    """Return the liquidation periods of the requested period's year and cadence.

    Modelo 303 liquidation periods are calendar quarters or, for monthly filers,
    calendar months (RD 1624/1992 art. 71.3); an annual token such as ``0A``
    belongs to Modelo 390 and refuses. The requested period and the cadence's
    terminal period are each resolved through the canonical revision selector at
    their own end date, so an undeclared token refuses instead of silently
    becoming a non-settlement period.

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
    revision_for_context, _modelo_directory = _pinned_selection(authority)
    modelo = str(Modelo("303"))
    year = period.filing_year
    revision_for_context(modelo, filing_year=year, period=period.registry_token, on=period.end_date)
    same_cadence = m303_cadence_liquidation_periods(year, period.kind, authority=authority)
    if not same_cadence:
        raise RegistryValidationError(
            f"Modelo 303 declares no {period.kind.value} liquidation periods for {year}",
        )
    terminal = same_cadence[-1]
    if terminal.registry_token != period.registry_token:
        revision_for_context(modelo, filing_year=year, period=terminal.registry_token, on=terminal.end_date)
    return same_cadence


def _same_cadence_periods(
    revisions: Iterable[RevisionSelectionMetadata],
    *,
    year: int,
    kind: PeriodKind,
) -> tuple[Period, ...]:
    return tuple(
        candidate
        for revision in revisions
        for token in revision.period_selector.periods_for_year(year)
        if (candidate := Period.from_year_and_code(year, token)).kind is kind
    )


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
    terminal = m303_liquidation_periods(period, authority=authority)[-1]
    return 0 if terminal.registry_token == period.registry_token else None


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
    "m303_cadence_liquidation_periods",
    "m303_liquidation_periods",
]
