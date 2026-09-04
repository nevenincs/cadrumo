"""Pure regulatory IVA-compensation carry-forward logic for Modelo 303.

This module owns the typed period-state and carry-forward-lot records, the
FIFO projection that turns filed-period states into source-period lots, and
the four-year-window expiry policy. All logic here is pure: it depends only on
:mod:`decimal`, :mod:`datetime`, pydantic, and :data:`STRICT_FROZEN_CONFIG`
from :mod:`cadrumo.core`. Repositories, port adapters, and orchestration that wire
these pure pieces to persistence live in the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.decimal.constants import ZERO
from ...core.filing_year import FilingYear
from ...core.identity import AeatExpedienteId, ContentDigest, SubjectTaxId
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period, PeriodKind, StandardPeriodCode
from ...core.time.utc import UtcInstant
from .errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationYearRangeError,
)

#: The provenances whose rows declare an opening carry-forward balance rather
#: than generating credit in a filed period. Both members belong here: the
#: retired ``status`` literal wrote one token for a seed AND a correction, so
#: branching on it silently treated the two as one path.
_OPERATOR_DECLARED_PROVENANCES = frozenset(
    {
        IvaCompensationStateProvenance.OPERATOR_SEED,
        IvaCompensationStateProvenance.OPERATOR_CORRECTION,
    },
)


class IvaCompensationExpiryReviewState(StrEnum):
    """Review state for an IVA compensation carry-forward lot."""

    ACTIVE = "active"
    EXPIRY_REVIEW_DUE = "expiry_review_due"
    EXPIRED_REVIEW_REQUIRED = "expired_review_required"


class IvaCompensationPeriodState(BaseModel):
    """Latest known Modelo 303 compensation state for one filed period."""

    model_config = _STRICT_FROZEN

    taxpayer_nif: SubjectTaxId | None = Field(
        default=None,
        description=(
            "The filing subject, validated through the canonical Spanish "
            "tax-identifier authority. None is the declared 'subject not "
            "carried' case: the annual-partition reconstruction rebuilds "
            "period states from casilla observations, which record no "
            "taxpayer, and those states are computational scaffold that is "
            "never persisted. Every state that IS persisted or surfaced to an "
            "operator carries a real identifier, and a malformed one is "
            "refused here rather than reaching carry-forward, wallet-balance "
            "or live-history consumers as if it identified the subject."
        ),
    )
    filing_year: FilingYear
    period: Period
    provenance: IvaCompensationStateProvenance = Field(
        description=(
            "Which of the five supplying paths built this row. Required with no "
            "default, so a new supplying path must declare its own provenance "
            "rather than inherit one it never chose. Constrained against "
            "expediente_id and status by the validator below."
        ),
    )
    expediente_id: AeatExpedienteId | None = Field(
        default=None,
        description=(
            "The AEAT-issued expediente: present on an AEAT capture, None on "
            "every other path. The four non-AEAT paths each used to mint a "
            "synthetic marker into this field (manual-seed, manual-correction, "
            "local-<ref>, obs-<year>-<period>), which made an operator-supplied "
            "string structurally indistinguishable from an identifier AEAT "
            "issued. Nothing is lost by dropping them: each was a lossier "
            "duplicate of the source_observation_key written at the same site."
        ),
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "The AEAT-PRINTED register status, and nothing else. None on every "
            "non-AEAT path. This field once carried three incompatible subjects "
            "at once -- an AEAT register status, an observation source-kind "
            "token, and two app lifecycle literals -- so provenance was readable "
            "off two fields that could disagree, and an operator seed was "
            "indistinguishable from an operator correction because both wrote "
            "the same literal. Provenance now has its own typed field."
        ),
    )
    presented_at: UtcInstant
    prior_pending_amount: Decimal | None = None
    applied_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    pending_for_later_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    period_result_amount: Decimal | None = None
    final_result_amount: Decimal | None = None
    generated_amount: Decimal = Field(ge=Decimal("0"))
    available_end_amount: Decimal = Field(ge=Decimal("0"))
    source_observation_key: str = Field(min_length=1, max_length=96)
    source_artefact_sha256: ContentDigest | None = Field(
        default=None,
        description=(
            "SHA-256 of the filed artefact this state was read from, typed "
            "through the canonical content-digest authority. None is the "
            "declared 'no artefact captured' case -- a registry-observation "
            "or manually seeded state carries no submitted file. A value that "
            "IS present identifies content-addressed evidence, so it must "
            "carry the canonical lowercase hex-64 shape: a 64-character "
            "non-digest would otherwise be persisted alongside valid "
            "compensation history and later be resolved as if it addressed "
            "the artefact."
        ),
    )

    @model_validator(mode="after")
    def _expediente_and_status_match_provenance(self) -> IvaCompensationPeriodState:
        is_aeat = self.provenance is IvaCompensationStateProvenance.AEAT_CAPTURE
        if is_aeat and self.expediente_id is None:
            raise ValueError(
                "an aeat_capture compensation state must carry the AEAT-issued expediente_id",
            )
        if not is_aeat and self.expediente_id is not None:
            raise ValueError(
                f"a {self.provenance.value} compensation state must not carry an "
                "expediente_id: only an AEAT capture receives one from AEAT",
            )
        if not is_aeat and self.status is not None:
            raise ValueError(
                f"a {self.provenance.value} compensation state must not carry a "
                "status: that field reports the AEAT-printed register status only",
            )
        return self

    @model_validator(mode="after")
    def _period_year_matches(self) -> IvaCompensationPeriodState:
        if self.period.filing_year != self.filing_year:
            raise ValueError("period.filing_year must match filing_year")
        return self


class IvaCompensationCarryForwardLot(BaseModel):
    """One generated IVA compensation balance tracked from its source period."""

    model_config = _STRICT_FROZEN

    taxpayer_nif: SubjectTaxId | None = Field(
        default=None,
        description=(
            "The filing subject carried through from the source period state; "
            "None where that state declared no subject (see "
            ":class:`IvaCompensationPeriodState`)."
        ),
    )
    source_filing_year: FilingYear
    source_period: Period
    generated_amount: Decimal = Field(ge=ZERO)
    applied_amount: Decimal = Field(ge=ZERO)
    remaining_amount: Decimal = Field(ge=ZERO)
    age_years: NonNegativeInt
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

    as_of_year: FilingYear
    lots: tuple[IvaCompensationCarryForwardLot, ...]
    unallocated_applied_amount: Decimal = Field(ge=ZERO)


@dataclass(slots=True)
class _WorkingCarryForwardLot:
    """Mutable accumulator for one generated lot during FIFO allocation."""

    taxpayer_nif: str | None
    source_filing_year: int
    source_period: Period
    generated_amount: Decimal
    applied_amount: Decimal
    remaining_amount: Decimal
    source_observation_key: str


def derive_303_compensation_available(
    *,
    posterior: Decimal,
    resultado: Decimal,
    refunded: bool = False,
) -> Decimal:
    """Modelo 303 end-of-period available compensation carry-forward.

    ``available`` equals ``iva.compensacion-pendiente-periodos-posteriores``
    (AEAT box 87) plus generated, where generated is
    ``max(0, -iva.resultado)`` (AEAT box 69). A negative result (a quota a
    compensar) generates new carry-forward; a positive result generates none.

    When ``refunded`` is ``True`` the period's negative result is requested as
    devolución (fichero "Tipo de declaración" ``D``) rather than carried forward:
    the generated credit is excluded from compensación carry, so the GENERATED
    component is zero and ``available = posterior`` only (for a full monthly/annual
    devolución request the posterior is also zero, so the period carries nothing).
    The default ``False`` keeps the standard compensación (``C``) behaviour, where
    the negative result generates the carry. Legal basis: RD 1624/1992 art. 30 /
    Ley 37/1992 art. 116 — a devolución-requested credit is not carried.
    """
    generated = ZERO if refunded else max(ZERO, -resultado)
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
    ordered = tuple(sorted(states, key=lambda item: (item.filing_year, iva_compensation_period_sort_key(item.period))))
    working: list[_WorkingCarryForwardLot] = []
    unallocated_applied = ZERO
    for state in ordered:
        applied = state.applied_amount or ZERO
        remaining_to_allocate = applied
        for lot in working:
            if remaining_to_allocate <= ZERO:
                break
            consumed = min(lot.remaining_amount, remaining_to_allocate)
            lot.applied_amount = lot.applied_amount + consumed
            lot.remaining_amount = lot.remaining_amount - consumed
            remaining_to_allocate -= consumed
        if remaining_to_allocate > ZERO:
            unallocated_applied += remaining_to_allocate
        # A filed period contributes a lot equal to the credit it GENERATED this
        # period. An operator-declared opening balance generated nothing in a
        # filed period (generated_amount == 0) but declares a prior carry-forward
        # in available_end_amount; surface that balance as a lot too, so
        # `iva-wallet balance` reflects it (lot_count > 0) instead of reporting an
        # empty wallet. The two cases are mutually exclusive (an operator-declared
        # opening balance never carries generated_amount), so no double-counting.
        lot_amount = state.generated_amount
        if lot_amount <= ZERO and state.provenance in _OPERATOR_DECLARED_PROVENANCES:
            lot_amount = state.available_end_amount
        if lot_amount > ZERO:
            working.append(
                _WorkingCarryForwardLot(
                    taxpayer_nif=state.taxpayer_nif,
                    source_filing_year=state.filing_year,
                    source_period=state.period,
                    generated_amount=lot_amount,
                    applied_amount=ZERO,
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
    """Modelo 390 year-end carry fields as one FIFO partition.

    The two AEAT annual carry-forward boxes partition the year's pending
    compensation credit governed by FIFO application netting across the whole
    ejercicio; they are NOT two independent per-period sums:

    - ``last_period_amount`` (``iva.anual.compensacion-ultimo-periodo-97``,
      AEAT box 97, "Resultado de la última autoliquidación. A compensar") is
      the saldo the LAST filed period carries forward — the year-generated
      remaining credit still pending at the end of the last period's
      autoliquidación (its disponible, net of any prior-year credit still
      pending).
    - ``generated_not_in_last_amount`` (``iva.anual.compensacion-generada-ejercicio-no-97``,
      AEAT box 662, "Cuotas a compensar generadas en el ejercicio, distintas a
      las incluidas en [97]") is the
      remaining of credits GENERATED in the ejercicio that did NOT carry into
      the last period's autoliquidación (e.g. a credit refunded in an
      intervening period, so it left the carry chain) — explicitly the year's
      pending credit not included in AEAT box 97.

    Applied credits appear in NEITHER box. The AEAT annual identity
    ``[86] = [95] − [97] − [98] − [662]`` binds the pair: box 97 + box 662 must
    equal the year's total pending with no double-count and no drop, so
    ``total_year_remaining_amount == last_period_amount +
    generated_not_in_last_amount`` always holds.
    """

    model_config = _STRICT_FROZEN

    filing_year: FilingYear
    last_period_amount: Decimal = Field(ge=ZERO)
    generated_not_in_last_amount: Decimal = Field(ge=ZERO)
    total_year_remaining_amount: Decimal = Field(ge=ZERO)

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
    """Partition the year's pending compensation credit into the Modelo 390 annual carry ids.

    Drives BOTH year-end carry boxes from the single FIFO projection
    (``report``) plus the year's filed period states, so they partition the
    year's pending credit with no double-count and no drop (the AEAT identity).

    The discriminator between ``iva.anual.compensacion-ultimo-periodo-97``
    (AEAT box 97, carried into the last period) and
    ``iva.anual.compensacion-generada-ejercicio-no-97`` (AEAT box 662,
    generated-but-not-carried) is the last filed period's available
    carry-forward saldo (``available_end_amount`` =
    ``iva.compensacion-pendiente-periodos-posteriores`` + generated):

    - ``iva.anual.compensacion-ultimo-periodo-97`` = the year-generated credit
      carried into the last period — the last filed period's disponible
      (``available_end_amount``) capped at the year's total remaining (the
      disponible may also carry prior-YEAR credit, which AEAT box 97 must not
      double-count, hence the cap).
    - ``iva.anual.compensacion-generada-ejercicio-no-97`` = the rest of the year's remaining credit (generated in the
      ejercicio but not carried into the last period's autoliquidación).

    In the common always-carry case every pending credit flows forward into the
    last period, so ``iva.anual.compensacion-ultimo-periodo-97`` collapses to the
    whole year's remaining and ``iva.anual.compensacion-generada-ejercicio-no-97``
    is zero. When a period's credit does NOT carry into the last period (it left
    the chain), that remaining lands in ``iva.anual.compensacion-generada-ejercicio-no-97``.

    Returns an :class:`IvaCompensationYearEndCarryPartition`.
    """
    if not 2000 <= filing_year <= 2099:
        raise IvaCompensationYearRangeError(
            translated_message="errors.refused.refused_iva_compensation_year_range",
            context={"filing_year": filing_year, "min_year": 2000, "max_year": 2099},
        )
    total_year_remaining = sum(
        (lot.remaining_amount for lot in report.lots if lot.source_filing_year == filing_year),
        ZERO,
    )
    year_states = sorted(
        (state for state in period_states if state.filing_year == filing_year),
        key=lambda state: iva_compensation_period_sort_key(state.period),
    )
    last_disponible = year_states[-1].available_end_amount if year_states else ZERO
    # The last period's disponible is the year credit it carries forward
    # (iva.anual.compensacion-ultimo-periodo-97, AEAT box 97); it may ALSO carry
    # prior-YEAR credit still pending, which that annual carry id must not
    # double-count, so cap at the year's own total remaining. Everything the
    # year generated but the last period did not carry (it left the chain) is
    # iva.anual.compensacion-generada-ejercicio-no-97 — the remainder of the partition.
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
        if lot.remaining_amount > ZERO
        and lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    )
    if expired:
        first = expired[0]
        raise IvaCompensationCarryForwardPolicyError(
            translated_message="errors.refused.refused_filing_calculate",
            context={
                "source_filing_year": str(first.source_filing_year),
                "source_period": first.source_period.registry_token,
                "remaining_balance_expired": True,
            },
        )
    return report


def iva_compensation_period_sort_key(period: Period) -> tuple[int, str]:
    """Order one typed IVA filing period within its filing year.

    Quarterly and monthly Modelo 303 rows remain in their established ordinal
    order. The annual ``0A`` row is deliberately ordered after every periodic
    row; its generic calendar span begins in January, so date ordering would
    incorrectly put it before the year's filings. Unsupported period families
    follow the recognised IVA filing forms without being interpreted as a
    periodic IVA declaration.
    """
    if period.is_quarterly:
        quarter_ordinal = period.quarter_ordinal
        if quarter_ordinal is None:
            raise IvaCompensationCarryForwardPolicyError(
                translated_message="errors.refused.refused_filing_calculate",
                context={"period": period.registry_token, "quarter_ordinal_present": False},
            )
        return (quarter_ordinal, period.registry_token)
    if period.kind is PeriodKind.MONTHLY:
        return (int(period.registry_token), period.registry_token)
    if period.standard_code is StandardPeriodCode.ANNUAL:
        return (99, period.registry_token)
    return (100, period.registry_token)


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
