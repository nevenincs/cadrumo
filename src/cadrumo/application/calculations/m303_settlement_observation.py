"""Read the persisted Modelo 303 observation of a year's annual settlement liquidation.

The annual prorrata and capital-goods regularisations belong to the last
liquidation of the calendar year (LIVA arts. 105.Cuatro and 110): the fourth
quarter for a quarterly filer and month 12 for a monthly filer (RD 1624/1992
art. 71.3). A reader with no liquidation period of its own -- the Modelo 390
annual summary -- does not know which cadence the filer used, so this module
asks each cadence the registry declares for the year for its terminal period
and admits exactly one filed settlement observation. None, several, or one
whose revision stamp cannot be re-confirmed stays a typed outcome naming the
periods concerned; it is never read as an absent or zero value.

See Also:
    :func:`~domain.iva.m303_settlement.m303_cadence_liquidation_periods`
        Registry period selection the terminal periods are read from.
    :func:`~application.calculations.revision_carry_gate.revision_carry_outcome`
        Shared re-confirmation of a carried observation's revision stamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...core.period import Period, PeriodKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.iva.m303_settlement import m303_cadence_liquidation_periods
from .observations_repository import CalculationObservationRepositoryProtocol, ObservationEnvelopePayload
from .revision_carry_gate import revision_carry_outcome

_M303_CADENCES: tuple[PeriodKind, ...] = (PeriodKind.QUARTERLY, PeriodKind.MONTHLY)


class M303SettlementObservationState(StrEnum):
    """Why a year's settlement observation was or was not admitted."""

    ADMITTED = "admitted"
    MISSING = "missing"
    REFUSED = "refused"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class M303SettlementObservation:
    """The outcome of reading one year's Modelo 303 settlement observation.

    ``periods`` names the terminal periods the outcome speaks of: the admitted
    or refused period, every declared terminal period when none was filed, or
    every filed terminal period when more than one cadence was filed.
    """

    state: M303SettlementObservationState
    periods: tuple[Period, ...]
    payload: ObservationEnvelopePayload | None = None


def m303_annual_settlement_observation(
    repository: CalculationObservationRepositoryProtocol,
    *,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> M303SettlementObservation:
    """Return the year's filed Modelo 303 settlement observation, or why it is unavailable."""
    modelo = form_for_role("iva.periodic")
    terminals: tuple[Period, ...] = tuple(
        periods[-1]
        for kind in _M303_CADENCES
        if (periods := m303_cadence_liquidation_periods(filing_year, kind, authority=operation))
    )
    filed: tuple[tuple[Period, ObservationEnvelopePayload], ...] = tuple(
        (period, payload)
        for period in terminals
        if (payload := repository.load_observation(modelo, period)) is not None
    )
    if not filed:
        return M303SettlementObservation(state=M303SettlementObservationState.MISSING, periods=terminals)
    (period, payload), *others = filed
    if others:
        return M303SettlementObservation(
            state=M303SettlementObservationState.AMBIGUOUS,
            periods=tuple(filed_period for filed_period, _payload in filed),
        )
    if revision_carry_outcome(payload.registry_snapshot_ref, operation=operation).refused:
        return M303SettlementObservation(state=M303SettlementObservationState.REFUSED, periods=(period,))
    return M303SettlementObservation(
        state=M303SettlementObservationState.ADMITTED,
        periods=(period,),
        payload=payload,
    )


__all__ = [
    "M303SettlementObservation",
    "M303SettlementObservationState",
    "m303_annual_settlement_observation",
]
