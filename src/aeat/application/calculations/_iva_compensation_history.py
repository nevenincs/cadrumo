"""Profile-scoped IVA compensation history built from filed Modelo 303s.

Records are stored at :class:`SensitivityClass` ``AUDIT`` under the IVA
compensation history namespace. The repository exposes typed
:class:`IvaCompensationPeriodState` objects; carry-forward projection is
produced by :func:`build_iva_compensation_carry_forward_report`.

This module uses :class:`IvaCompensationAnnualSummary` and :class:`IvaCompensationAnnualCrossCheck`
for annual cross-checking.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    IVA_COMPENSATION_HISTORY_NAMESPACE,
    SensitivityClass,
    safe_repository_id,
)
from ...core import Modelo
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core.time import now
from ...domain.iva_compensation._carry_forward import (
    IvaCompensationCarryForwardReport,
    IvaCompensationPeriodState,
    _period_sort_key,
)
from ...domain.iva_compensation._errors import (
    IvaCompensationDecimalParseError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)
from ._errors import IvaCompensationModeloError
from ._ports import FiledDeclaracionObservationProtocol

_ZERO = Decimal("0")


class IvaCompensationAnnualSummary(BaseModel):
    """Filed Modelo 390 annual IVA compensation summary for cross-checking."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    filing_year: int = Field(ge=2000, le=2099)
    expediente_id: str = Field(min_length=1, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    presented_at: datetime
    last_period_compensation_amount: Decimal = Field(ge=_ZERO)
    generated_not_in_last_period_amount: Decimal = Field(ge=_ZERO)
    total_pending_amount: Decimal = Field(ge=_ZERO)
    source_observation_key: str = Field(min_length=1, max_length=96)
    source_artefact_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class IvaCompensationAnnualCrossCheck(BaseModel):
    """Comparison between Modelo 303 carry-forward lots and a filed Modelo 390 summary."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    filing_year: int = Field(ge=2000, le=2099)
    carry_forward_remaining_amount: Decimal = Field(ge=_ZERO)
    modelo_390_total_pending_amount: Decimal = Field(ge=_ZERO)
    expected_last_period_compensation_amount: Decimal = Field(ge=_ZERO)
    expected_generated_not_in_last_period_amount: Decimal = Field(ge=_ZERO)
    difference_amount: Decimal
    last_period_difference_amount: Decimal
    generated_not_in_last_period_difference_amount: Decimal
    matches: bool
    mismatched_casillas: tuple[str, ...] = ()
    expiry_review_states: tuple[str, ...] = ()
    summary_source_observation_key: str = Field(min_length=1, max_length=96)


def iva_compensation_period_key(filing_year: int, period: str) -> str:
    """Return the latest-state key for one Modelo 303 period."""
    safe_repository_id(period, context="period")
    if not 2000 <= filing_year <= 2099:
        raise IvaCompensationYearRangeError(
            translated_message="errors.refused.refused_iva_compensation_year_range",
            context={"filing_year": filing_year, "min_year": 2000, "max_year": 2099},
        )
    return f"303:{filing_year}:{period}"


class IvaCompensationHistoryRepository(SecureBoundRepository[IvaCompensationPeriodState]):
    """Encrypted profile-local store of Modelo 303 IVA compensation history."""

    namespace: ClassVar[str] = IVA_COMPENSATION_HISTORY_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_COMPENSATION_HISTORY_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_COMPENSATION_HISTORY_NAMESPACE.schema_version
    payload_type: ClassVar[type[IvaCompensationPeriodState]] = IvaCompensationPeriodState

    @override
    def extract_identifier(self, payload: IvaCompensationPeriodState) -> str:
        return iva_compensation_period_key(payload.filing_year, payload.period)

    def load_period(self, filing_year: int, period: str) -> IvaCompensationPeriodState | None:
        """Return latest stored state for one period.

        Returns an :class:`IvaCompensationPeriodState` when a record exists,
        or ``None`` when none has been persisted for the given period.
        """
        return self.load(iva_compensation_period_key(filing_year, period))

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist latest stored state for one period."""
        self.save(state)

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Return all stored states as a tuple of :class:`IvaCompensationPeriodState` in chronological filing order."""
        return tuple(sorted(self.iter_records(), key=lambda item: (item.filing_year, _period_sort_key(item.period))))


_SEED_STATUS = "seeded"
_SEED_EXPEDIENTE_ID = "manual-seed"
_SEED_SOURCE_OBS_PREFIX = "303:seed"


def seed_iva_compensation_period(
    *,
    taxpayer_nif: str,
    filing_year: int,
    period: str,
    amount: Decimal,
    repository: IvaCompensationHistoryRepository | None = None,
    seeded_at: datetime | None = None,
) -> IvaCompensationPeriodState:
    """Persist a manually declared carry-forward balance for one Modelo 303 period.

    Returns an :class:`IvaCompensationPeriodState`.

    Intended for first-time users whose historical M303 carry-forward pre-dates
    the local compensation history. The seeded state is structurally identical
    to a filed-observation state but carries ``status='seeded'`` and synthetic
    provenance so downstream diagnostics can distinguish seed from filed records.

    Raises ``IvaCompensationSeedConflictError`` if a state already exists for
    the specified period — seeding must not overwrite an existing record.
    """
    repo = repository if repository is not None else IvaCompensationHistoryRepository()
    existing = repo.load_period(filing_year, period)
    if existing is not None:
        raise IvaCompensationSeedConflictError(
            translated_message="application.calculations.iva_compensation.errors.seed_conflict",
            context={"filing_year": filing_year, "period": period, "existing_status": existing.status},
        )
    when = seeded_at if seeded_at is not None else now()
    state = IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        filing_year=filing_year,
        period=period,
        expediente_id=_SEED_EXPEDIENTE_ID,
        status=_SEED_STATUS,
        presented_at=when,
        prior_pending_amount=None,
        applied_amount=None,
        pending_for_later_amount=amount,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=_ZERO,
        available_end_amount=amount,
        source_observation_key=f"{_SEED_SOURCE_OBS_PREFIX}:{filing_year}:{period}",
        source_artefact_sha256=None,
    )
    repo.save_period(state)
    return state


def iva_compensation_state_from_filed_observation(
    observation: FiledDeclaracionObservationProtocol,
) -> IvaCompensationPeriodState:
    """Build and return an :class:`IvaCompensationPeriodState` from a filed Modelo 303 observation."""
    if observation.modelo != Modelo.M303.value:
        raise IvaCompensationModeloError(
            translated_message="application.calculations.iva_compensation.errors.modelo_303_only",
            context={"modelo": observation.modelo},
        )
    values = _decimal_casilla_values(observation)
    result = _casilla_value(values, "69", "iva.resultado")
    posterior = _casilla_value(values, "87", "iva.compensacion-pendiente-periodos-posteriores")
    generated = max(Decimal("0"), -result) if result is not None else Decimal("0")
    available = _casilla_value(values, "iva.compensacion-disponible-fin-periodo")
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
        prior_pending_amount=_casilla_value(values, "110", "iva.compensacion-pendiente-periodos-anteriores"),
        applied_amount=_casilla_value(values, "78", "iva.compensacion-aplicada-periodo"),
        pending_for_later_amount=posterior,
        period_result_amount=result,
        final_result_amount=_casilla_value(values, "71"),
        generated_amount=generated,
        available_end_amount=available,
        source_observation_key=f"303:{observation.ejercicio}:{observation.period}:{observation.expediente_id}",
        source_artefact_sha256=source_artefact_sha256,
    )


def iva_compensation_annual_summary_from_filed_observation(
    observation: FiledDeclaracionObservationProtocol,
) -> IvaCompensationAnnualSummary:
    """Build an :class:`IvaCompensationAnnualSummary` from a filed Modelo 390 observation.

    Casilla 97 carries the final-period amount to compensate. Casilla 662
    carries generated pending compensation from the exercise that is not
    included in casilla 97. The summary is evidence for cross-checking the
    Modelo 303 carry-forward projection; it is not stored as a period state.
    """
    if observation.modelo != Modelo.M390.value:
        raise IvaCompensationModeloError(
            translated_message="application.calculations.iva_compensation.errors.modelo_390_only",
            context={"modelo": observation.modelo},
        )
    values = _decimal_casilla_values(observation)
    last_period = _casilla_value(values, "97", "iva.anual.compensacion-ultimo-periodo-97") or _ZERO
    generated_not_in_last = _casilla_value(values, "662", "iva.anual.compensacion-generada-ejercicio-no-97") or _ZERO
    source_artefact_sha256 = next(
        (artefact.sha256 for artefact in observation.artefacts if artefact.kind == "submitted_file"),
        None,
    )
    return IvaCompensationAnnualSummary(
        taxpayer_nif=observation.authenticated_identity,
        filing_year=observation.ejercicio,
        expediente_id=observation.expediente_id,
        status=observation.status,
        presented_at=observation.presented_at,
        last_period_compensation_amount=last_period,
        generated_not_in_last_period_amount=generated_not_in_last,
        total_pending_amount=last_period + generated_not_in_last,
        source_observation_key=f"390:{observation.ejercicio}:0A:{observation.expediente_id}",
        source_artefact_sha256=source_artefact_sha256,
    )


def cross_check_iva_compensation_annual_summary(
    report: IvaCompensationCarryForwardReport,
    summary: IvaCompensationAnnualSummary,
) -> IvaCompensationAnnualCrossCheck:
    """Compare projections with filed evidence and return an :class:`IvaCompensationAnnualCrossCheck`."""
    last_period = sum(
        (
            lot.generated_amount
            for lot in report.lots
            if lot.source_filing_year == summary.filing_year and lot.source_period.upper() == "4T"
        ),
        _ZERO,
    )
    generated_not_in_last = sum(
        (
            lot.remaining_amount
            for lot in report.lots
            if lot.source_filing_year == summary.filing_year and lot.source_period.upper() != "4T"
        ),
        _ZERO,
    )
    remaining = last_period + generated_not_in_last
    difference = remaining - summary.total_pending_amount
    last_period_difference = last_period - summary.last_period_compensation_amount
    generated_difference = generated_not_in_last - summary.generated_not_in_last_period_amount
    mismatches = tuple(
        casilla for casilla, drift in (("97", last_period_difference), ("662", generated_difference)) if drift != _ZERO
    )
    return IvaCompensationAnnualCrossCheck(
        filing_year=summary.filing_year,
        carry_forward_remaining_amount=remaining,
        modelo_390_total_pending_amount=summary.total_pending_amount,
        expected_last_period_compensation_amount=last_period,
        expected_generated_not_in_last_period_amount=generated_not_in_last,
        difference_amount=difference,
        last_period_difference_amount=last_period_difference,
        generated_not_in_last_period_difference_amount=generated_difference,
        matches=difference == _ZERO and not mismatches,
        mismatched_casillas=mismatches,
        expiry_review_states=tuple(str(lot.expiry_review_state) for lot in report.lots),
        summary_source_observation_key=summary.source_observation_key,
    )


def _decimal_casilla_values(observation: FiledDeclaracionObservationProtocol) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            continue
        try:
            values[casilla.casilla_id] = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise IvaCompensationDecimalParseError(
                translated_message="errors.refused.refused_iva_compensation_decimal_parse",
                context={"casilla_id": casilla.casilla_id},
            ) from exc
    return values


def _casilla_value(values: dict[str, Decimal], *casilla_ids: str) -> Decimal | None:
    for casilla_id in casilla_ids:
        value = values.get(casilla_id)
        if value is not None:
            return value
    return None


__all__ = [
    "IvaCompensationAnnualCrossCheck",
    "IvaCompensationAnnualSummary",
    "IvaCompensationHistoryRepository",
    "cross_check_iva_compensation_annual_summary",
    "iva_compensation_annual_summary_from_filed_observation",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
    "seed_iva_compensation_period",
]
