"""Profile-scoped IVA compensation history built from filed Modelo 303s."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.outbound.aeat.sede import FiledDeclaracionObservation
from ...adapters.persistence.storage import SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...core.errors import AeatError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_ZERO = Decimal("0")


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
    period: str = Field(min_length=1, max_length=8)
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


class IvaCompensationCarryForwardLot(BaseModel):
    """One generated IVA compensation balance tracked from its source period."""

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    source_filing_year: int = Field(ge=2000, le=2099)
    source_period: str = Field(min_length=1, max_length=8)
    generated_amount: Decimal = Field(ge=_ZERO)
    applied_amount: Decimal = Field(ge=_ZERO)
    remaining_amount: Decimal = Field(ge=_ZERO)
    age_years: int = Field(ge=0)
    expiry_review_state: IvaCompensationExpiryReviewState
    source_observation_key: str = Field(min_length=1, max_length=96)

    @model_validator(mode="after")
    def _amounts_balance(self) -> IvaCompensationCarryForwardLot:
        if self.applied_amount + self.remaining_amount != self.generated_amount:
            raise ValueError("applied_amount + remaining_amount must equal generated_amount")
        return self


class IvaCompensationCarryForwardReport(BaseModel):
    """Carry-forward lot projection from filed Modelo 303 compensation history."""

    model_config = _STRICT_FROZEN

    as_of_year: int = Field(ge=2000, le=2099)
    lots: tuple[IvaCompensationCarryForwardLot, ...]
    unallocated_applied_amount: Decimal = Field(ge=_ZERO)


class IvaCompensationCarryForwardPolicyError(AeatError, ValueError):
    """Raised when IVA compensation carry-forward lots violate policy."""


def iva_compensation_period_key(filing_year: int, period: str) -> str:
    """Return the latest-state key for one Modelo 303 period."""

    safe_repository_id(period, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ValueError(f"IVA compensation filing_year {filing_year} out of supported range [2000, 2099]")
    return f"303:{filing_year}:{period}"


@dataclass(slots=True)
class _WorkingCarryForwardLot:
    """Mutable accumulator for one generated lot during FIFO allocation."""

    taxpayer_nif: str
    source_filing_year: int
    source_period: str
    generated_amount: Decimal
    applied_amount: Decimal
    remaining_amount: Decimal
    source_observation_key: str


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
    """

    if not 2000 <= as_of_year <= 2099:
        raise ValueError(f"IVA compensation as_of_year {as_of_year} out of supported range [2000, 2099]")
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
        if state.generated_amount > _ZERO:
            working.append(
                _WorkingCarryForwardLot(
                    taxpayer_nif=state.taxpayer_nif,
                    source_filing_year=state.filing_year,
                    source_period=state.period,
                    generated_amount=state.generated_amount,
                    applied_amount=_ZERO,
                    remaining_amount=state.generated_amount,
                    source_observation_key=state.source_observation_key,
                )
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


def enforce_iva_compensation_four_year_window(
    report: IvaCompensationCarryForwardReport,
) -> IvaCompensationCarryForwardReport:
    """Refuse remaining IVA compensation lots beyond the four-year window."""

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
            f"from {first.source_filing_year}/{first.source_period}"
        )
    return report


class IvaCompensationHistoryRepository(SecureBoundRepository[IvaCompensationPeriodState]):
    """Encrypted profile-local store of Modelo 303 IVA compensation history."""

    namespace: ClassVar[str] = "aeat.calculations.iva_compensation.history"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[IvaCompensationPeriodState]] = IvaCompensationPeriodState

    def extract_identifier(self, payload: IvaCompensationPeriodState) -> str:
        return iva_compensation_period_key(payload.filing_year, payload.period)

    def load_period(self, filing_year: int, period: str) -> IvaCompensationPeriodState | None:
        """Return latest stored state for one period."""

        return self.load(iva_compensation_period_key(filing_year, period))

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist latest stored state for one period."""

        self.save(state)

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Return all stored states in chronological filing order."""

        return tuple(sorted(self.iter_records(), key=lambda item: (item.filing_year, _period_sort_key(item.period))))


def iva_compensation_state_from_filed_observation(
    observation: FiledDeclaracionObservation,
) -> IvaCompensationPeriodState:
    """Build one IVA compensation history state from a filed Modelo 303 observation."""

    if observation.modelo != "303":
        raise ValueError("IVA compensation history only accepts Modelo 303 observations")
    values = _decimal_casilla_values(observation)
    result = values.get("69")
    posterior = values.get("87")
    generated = max(Decimal("0"), -result) if result is not None else Decimal("0")
    available = values.get("iva.compensacion-disponible-fin-periodo")
    if available is None:
        available = (posterior or Decimal("0")) + generated
    source_artefact_sha256 = next(
        (artefact.sha256 for artefact in observation.artefacts if artefact.kind == "submitted_file"),
        None,
    )
    return IvaCompensationPeriodState(
        taxpayer_nif=observation.authenticated_identity,
        filing_year=observation.ejercicio,
        period=observation.period,
        expediente_id=observation.expediente_id,
        status=observation.status,
        presented_at=observation.presented_at,
        prior_pending_amount=values.get("110"),
        applied_amount=values.get("78"),
        pending_for_later_amount=posterior,
        period_result_amount=result,
        final_result_amount=values.get("71"),
        generated_amount=generated,
        available_end_amount=available,
        source_observation_key=f"303:{observation.ejercicio}:{observation.period}:{observation.expediente_id}",
        source_artefact_sha256=source_artefact_sha256,
    )


def _decimal_casilla_values(observation: FiledDeclaracionObservation) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            continue
        try:
            values[casilla.casilla_id] = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise ValueError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
    return values


def _period_sort_key(period: str) -> tuple[int, str]:
    upper = period.upper()
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
    "IvaCompensationCarryForwardPolicyError",
    "IvaCompensationCarryForwardReport",
    "IvaCompensationExpiryReviewState",
    "IvaCompensationHistoryRepository",
    "IvaCompensationPeriodState",
    "build_iva_compensation_carry_forward_report",
    "enforce_iva_compensation_four_year_window",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
]
