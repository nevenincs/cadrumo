"""Pure regulatory IVA-compensation carry-forward logic for Modelo 303.

This module owns the typed period-state and carry-forward-lot records, the
FIFO projection that turns filed-period states into source-period lots, and
the four-year-window expiry policy. All logic here is pure: it depends only on
:mod:`decimal`, :mod:`datetime`, pydantic, and :data:`STRICT_FROZEN_CONFIG`
from :mod:`aeat.core`. Repositories, port adapters, and orchestration that wire
these pure pieces to persistence live in the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ._errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationYearRangeError,
)

_ZERO = Decimal("0")

#: Status carried by a manually-seeded opening carry-forward state (written by
#: the application ``seed_iva_compensation_period`` helper). A seeded state
#: declares a prior carry-forward balance in ``available_end_amount`` /
#: ``pending_for_later_amount`` with ``generated_amount == 0`` (it generated no
#: new credit in a filed period); the lot builder must still surface it as an
#: available lot so ``iva-wallet balance`` reflects the seeded opening balance.
_SEEDED_STATUS = "seeded"


class IvaCompensationExpiryReviewState(StrEnum):
    """Review state for an IVA compensation carry-forward lot."""

    ACTIVE = "active"
    EXPIRY_REVIEW_DUE = "expiry_review_due"
    EXPIRED_REVIEW_REQUIRED = "expired_review_required"


class IvaCompensationPeriodState(BaseModel):
    """Latest known Modelo 303 compensation state for one filed period."""

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    expediente_id: str = Field(min_length=1, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    presented_at: datetime
    prior_pending_amount: Decimal | None = None
    applied_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    pending_for_later_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    period_result_amount: Decimal | None = None
    final_result_amount: Decimal | None = None
    generated_amount: Decimal = Field(ge=Decimal("0"))
    available_end_amount: Decimal = Field(ge=Decimal("0"))
    source_observation_key: str = Field(min_length=1, max_length=96)
    source_artefact_sha256: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def _period_year_matches(self) -> IvaCompensationPeriodState:
        if self.period.filing_year != self.filing_year:
            raise ValueError("period.filing_year must match filing_year")
        return self


class IvaCompensationCarryForwardLot(BaseModel):
    """One generated IVA compensation balance tracked from its source period."""

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    source_filing_year: int = Field(ge=2000, le=2099)
    source_period: Period
    generated_amount: Decimal = Field(ge=_ZERO)
    applied_amount: Decimal = Field(ge=_ZERO)
    remaining_amount: Decimal = Field(ge=_ZERO)
    age_years: int = Field(ge=0)
    expiry_review_state: IvaCompensationExpiryReviewState
    source_observation_key: str = Field(min_length=1, max_length=96)

    @model_validator(mode="after")
    def _amounts_balance(self) -> IvaCompensationCarryForwardLot:
        if self.source_period.filing_year != self.source_filing_year:
            raise ValueError("source_period.filing_year must match source_filing_year")
        if self.applied_amount + self.remaining_amount != self.generated_amount:
            raise ValueError("applied_amount + remaining_amount must equal generated_amount")
        return self


class IvaCompensationCarryForwardReport(BaseModel):
    """Carry-forward lot projection from filed Modelo 303 compensation history."""

    model_config = _STRICT_FROZEN

    as_of_year: int = Field(ge=2000, le=2099)
    lots: tuple[IvaCompensationCarryForwardLot, ...]
    unallocated_applied_amount: Decimal = Field(ge=_ZERO)


@dataclass(slots=True)
class _WorkingCarryForwardLot:
    """Mutable accumulator for one generated lot during FIFO allocation."""

    taxpayer_nif: str
    source_filing_year: int
    source_period: Period
    generated_amount: Decimal
    applied_amount: Decimal
    remaining_amount: Decimal
    source_observation_key: str


def derive_303_compensation_available(*, posterior: Decimal, resultado: Decimal) -> Decimal:
    """Modelo 303 end-of-period available compensation carry-forward.

    available = casilla 87 (compensación pendiente de periodos posteriores)
    plus generated, where generated = max(0, -casilla 69 (resultado)). A
    negative result (a quota a compensar) generates new carry-forward; a
    positive result generates none.
    """
    generated = max(Decimal("0"), -resultado)
    return posterior + generated


def build_iva_compensation_carry_forward_report(
    states: tuple[IvaCompensationPeriodState, ...],
    *,
    as_of_year: int,
) -> IvaCompensationCarryForwardReport:
    """Project filed-period compensation states into source-period lots.

    Applications of prior compensation are allocated FIFO across earlier
    generated lots. Current-period generation is added after any
    application recorded for that same period, matching Modelo 303's
    prior-balance-before-new-generation shape.

    Returns an :class:`IvaCompensationCarryForwardReport`.
    """
    if not 2000 <= as_of_year <= 2099:
        raise IvaCompensationYearRangeError(
            translated_message="errors.refused.refused_iva_compensation_year_range",
            context={"as_of_year": as_of_year, "min_year": 2000, "max_year": 2099},
        )
    ordered = tuple(sorted(states, key=lambda item: (item.filing_year, _period_sort_key(item.period))))
    working: list[_WorkingCarryForwardLot] = []
    unallocated_applied = _ZERO
    for state in ordered:
        applied = state.applied_amount or _ZERO
        remaining_to_allocate = applied
        for lot in working:
            if remaining_to_allocate <= _ZERO:
                break
            consumed = min(lot.remaining_amount, remaining_to_allocate)
            lot.applied_amount = lot.applied_amount + consumed
            lot.remaining_amount = lot.remaining_amount - consumed
            remaining_to_allocate -= consumed
        if remaining_to_allocate > _ZERO:
            unallocated_applied += remaining_to_allocate
        # A filed period contributes a lot equal to the credit it GENERATED this
        # period. A manually-seeded opening balance generated nothing in a filed
        # period (generated_amount == 0) but declares a prior carry-forward in
        # available_end_amount; surface that seeded balance as a lot too, so
        # `iva-wallet balance` reflects the seeded state (lot_count > 0) instead
        # of reporting an empty wallet. The two cases are mutually exclusive (a
        # seed never carries generated_amount), so no double-counting.
        lot_amount = state.generated_amount
        if lot_amount <= _ZERO and state.status == _SEEDED_STATUS:
            lot_amount = state.available_end_amount
        if lot_amount > _ZERO:
            working.append(
                _WorkingCarryForwardLot(
                    taxpayer_nif=state.taxpayer_nif,
                    source_filing_year=state.filing_year,
                    source_period=state.period,
                    generated_amount=lot_amount,
                    applied_amount=_ZERO,
                    remaining_amount=lot_amount,
                    source_observation_key=state.source_observation_key,
                ),
            )
    lots = tuple(
        IvaCompensationCarryForwardLot(
            taxpayer_nif=item.taxpayer_nif,
            source_filing_year=item.source_filing_year,
            source_period=item.source_period,
            generated_amount=item.generated_amount,
            applied_amount=item.applied_amount,
            remaining_amount=item.remaining_amount,
            age_years=max(0, as_of_year - item.source_filing_year),
            expiry_review_state=_expiry_review_state(
                source_filing_year=item.source_filing_year,
                as_of_year=as_of_year,
            ),
            source_observation_key=item.source_observation_key,
        )
        for item in working
    )
    return IvaCompensationCarryForwardReport(
        as_of_year=as_of_year,
        lots=lots,
        unallocated_applied_amount=unallocated_applied,
    )


class IvaCompensationYearEndCarryPartition(BaseModel):
    """Modelo 390 year-end carry boxes 97 and 662 as one FIFO partition.

    The two AEAT annual carry-forward boxes partition the year's pending
    compensation credit governed by FIFO application netting across the whole
    ejercicio; they are NOT two independent per-period sums:

    - ``last_period_amount`` (box 97, "Resultado de la última autoliquidación.
      A compensar") is the saldo the LAST filed period carries forward — the
      year-generated remaining credit still pending at the end of the last
      period's autoliquidación (its disponible, net of any prior-year credit
      still pending).
    - ``generated_not_in_last_amount`` (box 662, "Cuotas a compensar generadas
      en el ejercicio, distintas a las incluidas en la casilla 97") is the
      remaining of credits GENERATED in the ejercicio that did NOT carry into
      the last period's autoliquidación (e.g. a credit refunded in an
      intervening period, so it left the carry chain) — explicitly the year's
      pending credit "cuando NO esté incluida en la casilla 97".

    Applied credits appear in NEITHER box. The AEAT annual identity
    ``[86] = [95] − [97] − [98] − [662]`` binds the pair: box 97 + box 662 must
    equal the year's total pending with no double-count and no drop, so
    ``total_year_remaining_amount == last_period_amount +
    generated_not_in_last_amount`` always holds.
    """

    model_config = _STRICT_FROZEN

    filing_year: int = Field(ge=2000, le=2099)
    last_period_amount: Decimal = Field(ge=_ZERO)
    generated_not_in_last_amount: Decimal = Field(ge=_ZERO)
    total_year_remaining_amount: Decimal = Field(ge=_ZERO)

    @model_validator(mode="after")
    def _partition_sums(self) -> IvaCompensationYearEndCarryPartition:
        if self.last_period_amount + self.generated_not_in_last_amount != self.total_year_remaining_amount:
            raise ValueError("last_period_amount + generated_not_in_last_amount must equal total_year_remaining_amount")
        return self


def derive_iva_compensation_year_end_carry_partition(
    report: IvaCompensationCarryForwardReport,
    period_states: tuple[IvaCompensationPeriodState, ...],
    *,
    filing_year: int,
) -> IvaCompensationYearEndCarryPartition:
    """Partition the year's pending compensation credit into Modelo 390 boxes 97 and 662.

    Drives BOTH year-end carry boxes from the single FIFO projection
    (``report``) plus the year's filed period states, so they partition the
    year's pending credit with no double-count and no drop (the AEAT identity).

    The discriminator between box 97 (carried into the last period) and box 662
    (generated-but-not-carried) is the last filed period's available
    carry-forward saldo (``available_end_amount`` = casilla 87 + generated):

    - ``box 97`` = the year-generated credit carried into the last period —
      the last filed period's disponible (``available_end_amount``) capped at
      the year's total remaining (the disponible may also carry prior-YEAR
      credit, which box 97 must not double-count, hence the cap).
    - ``box 662`` = the rest of the year's remaining credit (generated in the
      ejercicio but not carried into the last period's autoliquidación).

    In the common always-carry case every pending credit flows forward into the
    last period, so box 97 collapses to the whole year's remaining and box 662
    is zero. When a period's credit does NOT carry into the last period (it left
    the chain), that remaining lands in box 662.

    Returns an :class:`IvaCompensationYearEndCarryPartition`.
    """
    if not 2000 <= filing_year <= 2099:
        raise IvaCompensationYearRangeError(
            translated_message="errors.refused.refused_iva_compensation_year_range",
            context={"filing_year": filing_year, "min_year": 2000, "max_year": 2099},
        )
    total_year_remaining = sum(
        (lot.remaining_amount for lot in report.lots if lot.source_filing_year == filing_year),
        _ZERO,
    )
    year_states = sorted(
        (state for state in period_states if state.filing_year == filing_year),
        key=lambda state: _period_sort_key(state.period),
    )
    last_disponible = year_states[-1].available_end_amount if year_states else _ZERO
    # The last period's disponible is the year credit it carries forward (box
    # 97); it may ALSO carry prior-YEAR credit still pending, which box 97 must
    # not double-count, so cap at the year's own total remaining. Everything the
    # year generated but the last period did not carry (it left the chain) is
    # box 662 — the remainder of the partition.
    last_period = min(last_disponible, total_year_remaining)
    generated_not_in_last = total_year_remaining - last_period
    return IvaCompensationYearEndCarryPartition(
        filing_year=filing_year,
        last_period_amount=last_period,
        generated_not_in_last_amount=generated_not_in_last,
        total_year_remaining_amount=total_year_remaining,
    )


def enforce_iva_compensation_four_year_window(
    report: IvaCompensationCarryForwardReport,
) -> IvaCompensationCarryForwardReport:
    """Refuse remaining IVA compensation lots beyond the four-year window.

    Returns the :class:`IvaCompensationCarryForwardReport` unchanged when
    all lots are within the window.
    """
    expired = tuple(
        lot
        for lot in report.lots
        if lot.remaining_amount > _ZERO
        and lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    )
    if expired:
        first = expired[0]
        raise IvaCompensationCarryForwardPolicyError(
            "IVA compensation carry-forward contains expired remaining balance "
            f"from {first.source_filing_year}/{first.source_period.registry_token}",
        )
    return report


def _period_sort_key(period: Period) -> tuple[int, str]:
    upper = period.registry_token
    if upper.endswith("T") and upper[:-1].isdigit():
        return (int(upper[:-1]), upper)
    if upper.isdigit():
        return (int(upper), upper)
    if upper == "0A":
        return (99, upper)
    return (100, upper)


def _expiry_review_state(
    *,
    source_filing_year: int,
    as_of_year: int,
) -> IvaCompensationExpiryReviewState:
    age_years = max(0, as_of_year - source_filing_year)
    if age_years > 4:
        return IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    if age_years == 4:
        return IvaCompensationExpiryReviewState.EXPIRY_REVIEW_DUE
    return IvaCompensationExpiryReviewState.ACTIVE


__all__ = [
    "IvaCompensationCarryForwardLot",
    "IvaCompensationCarryForwardReport",
    "IvaCompensationExpiryReviewState",
    "IvaCompensationPeriodState",
    "IvaCompensationYearEndCarryPartition",
    "build_iva_compensation_carry_forward_report",
    "derive_303_compensation_available",
    "derive_iva_compensation_year_end_carry_partition",
    "enforce_iva_compensation_four_year_window",
]
