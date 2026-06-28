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
from typing import ClassVar, Final, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    IVA_COMPENSATION_HISTORY_NAMESPACE,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core import Modelo, Period
from ...core.resources import resources
from ...core.time import now
from ...domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    undeclared_casilla_ids,
    validated_casilla_id,
)
from ...domain.iva_compensation._carry_forward import (
    IvaCompensationCarryForwardReport,
    IvaCompensationPeriodState,
    _period_sort_key,
    derive_iva_compensation_year_end_carry_partition,
)
from ...domain.iva_compensation._errors import (
    IvaCompensationCasillaReferenceError,
    IvaCompensationDecimalParseError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)
from ._errors import IvaCompensationModeloError
from ._ports import FiledDeclaracionObservationProtocol

_ZERO = Decimal("0")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="IVA compensation history casilla constant")
    except ValueError as exc:
        raise RuntimeError(f"IVA compensation history casilla constant {value!r} is not a CasillaId") from exc


_M303_RESULTADO_CASILLA: Final[CasillaId] = _casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-generada-periodo")
_M303_POSTERIOR_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_DISPONIBLE_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: Final[CasillaId] = (
    _casilla_id("iva.compensacion-pendiente-periodos-anteriores")
)
_M303_COMPENSACION_APLICADA_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-aplicada-periodo")
_M303_RESULTADO_FINAL_CASILLA: Final[CasillaId] = _casilla_id("71")
_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA: Final[CasillaId] = _casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
)
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: Final[CasillaId] = _casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
)


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
    mismatched_casilla_ids: tuple[CasillaId, ...] = ()
    expiry_review_states: tuple[str, ...] = ()
    summary_source_observation_key: str = Field(min_length=1, max_length=96)


def iva_compensation_period_key(period: Period) -> str:
    """Return the latest-state key for one Modelo 303 period."""
    safe_repository_id(period.registry_token, context="period")
    filing_year = period.filing_year
    if not 2000 <= filing_year <= 2099:
        raise IvaCompensationYearRangeError(
            translated_message="errors.refused.refused_iva_compensation_year_range",
            context={"filing_year": filing_year, "min_year": 2000, "max_year": 2099},
        )
    return f"303:{filing_year}:{period.registry_token}"


class IvaCompensationHistoryRepository(SecureBoundRepository[IvaCompensationPeriodState]):
    """Encrypted profile-local store of Modelo 303 IVA compensation history."""

    namespace: ClassVar[str] = IVA_COMPENSATION_HISTORY_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_COMPENSATION_HISTORY_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_COMPENSATION_HISTORY_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = IvaCompensationPeriodState

    @override
    def extract_identifier(self, payload: IvaCompensationPeriodState) -> str:
        return iva_compensation_period_key(payload.period)

    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Return latest stored state for one period.

        Returns an :class:`IvaCompensationPeriodState` when a record exists,
        or ``None`` when none has been persisted for the given period.
        """
        return self.load(iva_compensation_period_key(period))

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist latest stored state for one period."""
        self.save(state)

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Return all stored states as a tuple of :class:`IvaCompensationPeriodState` in chronological filing order."""
        return tuple(sorted(self.iter_records(), key=lambda item: (item.filing_year, _period_sort_key(item.period))))


_SEED_STATUS = "seeded"
_SEED_EXPEDIENTE_ID = "manual-seed"
_SEED_SOURCE_OBS_PREFIX = "303:seed"
_CORRECTED_EXPEDIENTE_ID = "manual-correction"
_CORRECTED_SOURCE_OBS_PREFIX = "303:correction"


def seed_iva_compensation_period(
    *,
    taxpayer_nif: str,
    period: Period,
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
    existing = repo.load_period(period)
    if existing is not None:
        raise IvaCompensationSeedConflictError(
            translated_message="application.calculations.iva_compensation.errors.seed_conflict",
            context={
                "filing_year": period.filing_year,
                "period": period.registry_token,
                "existing_status": existing.status,
            },
        )
    when = seeded_at if seeded_at is not None else now()
    state = IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        filing_year=period.filing_year,
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
        source_observation_key=f"{_SEED_SOURCE_OBS_PREFIX}:{period.filing_year}:{period.registry_token}",
        source_artefact_sha256=None,
    )
    repo.save_period(state)
    return state


def correct_iva_compensation_period(
    *,
    taxpayer_nif: str,
    period: Period,
    amount: Decimal,
    repository: IvaCompensationHistoryRepository | None = None,
    corrected_at: datetime | None = None,
) -> IvaCompensationPeriodState:
    """Overwrite a manually-seeded carry-forward balance for one Modelo 303 period.

    Returns the corrected :class:`IvaCompensationPeriodState`.

    The single-writer companion of :func:`seed_iva_compensation_period`: where
    seeding refuses if a record already exists, correction is the deliberate
    re-write path for a wrong opening compensation balance whose period
    pre-dates local history. It writes through the same
    :class:`IvaCompensationHistoryRepository` (no parallel write path), so the
    corrected state replaces the stored record at the same period key.

    The guard that a sealed (already-filed) Modelo 303 must not have its
    compensation basis silently changed lives one layer up, in the modelo
    application facade that resolves the bucket's taxpayer and revisions; this
    primitive is the unguarded write the facade delegates to once that guard has
    passed. It refuses to fabricate a record from nothing: an absent period is a
    seed, not a correction, and raises ``IvaCompensationSeedConflictError`` with
    a ``correction-on-missing`` marker so the facade can surface the seed-first
    guidance.
    """
    repo = repository if repository is not None else IvaCompensationHistoryRepository()
    existing = repo.load_period(period)
    if existing is None:
        raise IvaCompensationSeedConflictError(
            translated_message="application.calculations.iva_compensation.errors.correction_missing",
            context={"filing_year": period.filing_year, "period": period.registry_token, "existing_status": "absent"},
        )
    when = corrected_at if corrected_at is not None else now()
    state = IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        filing_year=period.filing_year,
        period=period,
        expediente_id=_CORRECTED_EXPEDIENTE_ID,
        status=_SEED_STATUS,
        presented_at=when,
        prior_pending_amount=None,
        applied_amount=None,
        pending_for_later_amount=amount,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=_ZERO,
        available_end_amount=amount,
        source_observation_key=f"{_CORRECTED_SOURCE_OBS_PREFIX}:{period.filing_year}:{period.registry_token}",
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
    source_artefact_sha256 = next(
        (artefact.sha256 for artefact in observation.artefacts if artefact.kind == "submitted_file"),
        None,
    )
    return _iva_compensation_state_from_values(
        values,
        taxpayer_nif=observation.authenticated_identity,
        filing_year=observation.ejercicio,
        period=observation.period,
        expediente_id=observation.expediente_id,
        status=observation.status,
        presented_at=observation.presented_at,
        source_observation_key=(
            f"303:{observation.ejercicio}:{observation.period.registry_token}:{observation.expediente_id}"
        ),
        source_artefact_sha256=source_artefact_sha256,
    )


def iva_compensation_state_from_registry_observation(
    observation: RegistryModeloObservation,
    *,
    taxpayer_nif: str,
    expediente_id: str,
    status: str,
    presented_at: datetime,
    source_observation_key: str | None = None,
    source_artefact_sha256: str | None = None,
) -> IvaCompensationPeriodState:
    """Build and return an :class:`IvaCompensationPeriodState` from a registry-grounded Modelo 303 observation."""
    if observation.modelo != Modelo.M303.value:
        raise IvaCompensationModeloError(
            translated_message="application.calculations.iva_compensation.errors.modelo_303_only",
            context={"modelo": observation.modelo},
        )
    _validate_registry_observation_casilla_ids(observation)
    period = observation.filing_period or Period.from_year_and_code(observation.filing_year, observation.period)
    key = source_observation_key or f"303:{observation.filing_year}:{period.registry_token}:{expediente_id}"
    return _iva_compensation_state_from_values(
        dict(observation.casilla_values),
        taxpayer_nif=taxpayer_nif,
        filing_year=observation.filing_year,
        period=period,
        expediente_id=expediente_id,
        status=status,
        presented_at=presented_at,
        source_observation_key=key,
        source_artefact_sha256=source_artefact_sha256,
    )


def iva_compensation_annual_summary_from_filed_observation(
    observation: FiledDeclaracionObservationProtocol,
) -> IvaCompensationAnnualSummary:
    """Build an :class:`IvaCompensationAnnualSummary` from a filed Modelo 390 observation.

    ``iva.anual.compensacion-ultimo-periodo-97`` carries the final-period amount
    to compensate. ``iva.anual.compensacion-generada-ejercicio-no-97`` carries
    generated pending compensation from the exercise that is not included in the
    final-period annual carry id. The summary is evidence for cross-checking the
    Modelo 303 carry-forward projection; it is not stored as a period state.
    """
    if observation.modelo != Modelo.M390.value:
        raise IvaCompensationModeloError(
            translated_message="application.calculations.iva_compensation.errors.modelo_390_only",
            context={"modelo": observation.modelo},
        )
    values = _decimal_casilla_values(observation)
    last_period = _resolve_casilla_value(values, _M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA) or _ZERO
    generated_not_in_last = _resolve_casilla_value(
        values,
        _M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
    ) or _ZERO
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
    *,
    period_states: tuple[IvaCompensationPeriodState, ...] = (),
) -> IvaCompensationAnnualCrossCheck:
    """Compare projections with filed evidence and return an :class:`IvaCompensationAnnualCrossCheck`.

    The expected ``iva.anual.compensacion-ultimo-periodo-97`` and
    ``iva.anual.compensacion-generada-ejercicio-no-97`` figures are derived
    through the SAME FIFO carry partition that drives the Modelo 390 calculation
    (:func:`derive_iva_compensation_year_end_carry_partition`), so the
    cross-check and both annual carry bindings cannot diverge: all three read
    one partition of the year's pending credit. ``period_states`` is the same
    tuple of filed Modelo 303 states the carry-forward ``report`` was built
    from; it supplies the last period's disponible that discriminates the
    final-period carry from the generated-not-carried amount.
    """
    partition = derive_iva_compensation_year_end_carry_partition(
        report,
        period_states,
        filing_year=summary.filing_year,
    )
    last_period = partition.last_period_amount
    generated_not_in_last = partition.generated_not_in_last_amount
    remaining = last_period + generated_not_in_last
    difference = remaining - summary.total_pending_amount
    last_period_difference = last_period - summary.last_period_compensation_amount
    generated_difference = generated_not_in_last - summary.generated_not_in_last_period_amount
    mismatches = tuple(
        casilla
        for casilla, drift in (
            (_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA, last_period_difference),
            (_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA, generated_difference),
        )
        if drift != _ZERO
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
        mismatched_casilla_ids=mismatches,
        expiry_review_states=tuple(str(lot.expiry_review_state) for lot in report.lots),
        summary_source_observation_key=summary.source_observation_key,
    )


def _iva_compensation_state_from_values(
    values: dict[CasillaId, Decimal],
    *,
    taxpayer_nif: str,
    filing_year: int,
    period: Period,
    expediente_id: str,
    status: str,
    presented_at: datetime,
    source_observation_key: str,
    source_artefact_sha256: str | None,
) -> IvaCompensationPeriodState:
    result = _resolve_casilla_value(values, _M303_RESULTADO_CASILLA)
    posterior = _resolve_casilla_value(values, _M303_POSTERIOR_CASILLA)
    generated = _resolve_casilla_value(values, _M303_GENERADA_CASILLA)
    if generated is None:
        generated = max(_ZERO, -result) if result is not None else _ZERO
    # Semantic-only casilla (no numeric AEAT box), so it was never an inline-number
    # routing literal — looked up directly by its registry id, behaviour-preserving.
    available = _casilla_value(values, _M303_DISPONIBLE_CASILLA)
    if available is None:
        available = (posterior or _ZERO) + generated
    return IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        filing_year=filing_year,
        period=period,
        expediente_id=expediente_id,
        status=status,
        presented_at=presented_at,
        prior_pending_amount=_resolve_casilla_value(values, _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA),
        applied_amount=_resolve_casilla_value(values, _M303_COMPENSACION_APLICADA_CASILLA),
        pending_for_later_amount=posterior,
        period_result_amount=result,
        final_result_amount=_resolve_casilla_value(values, _M303_RESULTADO_FINAL_CASILLA),
        generated_amount=generated,
        available_end_amount=available,
        source_observation_key=source_observation_key,
        source_artefact_sha256=source_artefact_sha256,
    )


def _decimal_casilla_values(observation: FiledDeclaracionObservationProtocol) -> dict[CasillaId, Decimal]:
    _validate_observed_casilla_ids(observation)
    values: dict[CasillaId, Decimal] = {}
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


def _validate_observed_casilla_ids(observation: FiledDeclaracionObservationProtocol) -> None:
    snapshot = resources().modelos.authority.snapshot(
        observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period.registry_token,
    )
    invalid = undeclared_casilla_ids(snapshot.revision, (casilla.casilla_id for casilla in observation.casillas))
    if not invalid:
        return
    raise IvaCompensationCasillaReferenceError(
        "IVA compensation observations must be keyed by canonical casilla.id values declared by the registry",
        context={
            "modelo": observation.modelo,
            "revision": snapshot.revision.id,
            "period": observation.period.registry_token,
            "casilla_ids": invalid,
        },
        translated_message="errors.refused.refused_calculations_casilla_constraint",
    )


def _validate_registry_observation_casilla_ids(observation: RegistryModeloObservation) -> None:
    snapshot = resources().modelos.authority.snapshot(
        observation.modelo,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    invalid = undeclared_casilla_ids(snapshot.revision, observation.casilla_values)
    if not invalid:
        return
    raise IvaCompensationCasillaReferenceError(
        "IVA compensation registry observations must be keyed by canonical casilla.id values declared by the registry",
        context={
            "modelo": observation.modelo,
            "revision": snapshot.revision.id,
            "period": observation.period,
            "casilla_ids": invalid,
        },
        translated_message="errors.refused.refused_calculations_casilla_constraint",
    )


def _casilla_value(values: dict[CasillaId, Decimal], *casilla_ids: CasillaId) -> Decimal | None:
    for casilla_id in casilla_ids:
        value = values.get(casilla_id)
        if value is not None:
            return value
    return None


def _resolve_casilla_value(values: dict[CasillaId, Decimal], semantic_id: CasillaId) -> Decimal | None:
    """Resolve a filed-observation casilla value by canonical ``casilla.id`` only."""
    return _casilla_value(values, semantic_id)


__all__ = [
    "IvaCompensationAnnualCrossCheck",
    "IvaCompensationAnnualSummary",
    "IvaCompensationHistoryRepository",
    "correct_iva_compensation_period",
    "cross_check_iva_compensation_annual_summary",
    "iva_compensation_annual_summary_from_filed_observation",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
    "iva_compensation_state_from_registry_observation",
    "seed_iva_compensation_period",
]
