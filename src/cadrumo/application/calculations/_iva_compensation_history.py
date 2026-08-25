"""Profile-scoped IVA compensation history built from filed Modelo 303s.

Records are stored at
:class:`~adapters.persistence.storage.SensitivityClass` ``AUDIT`` under
the
:data:`adapters.persistence.storage.IVA_COMPENSATION_HISTORY_NAMESPACE`.
The repository exposes typed
:class:`~domain.iva_compensation._carry_forward.IvaCompensationPeriodState`
objects; carry-forward projection is produced by
:func:`~domain.iva_compensation._carry_forward.build_iva_compensation_carry_forward_report`.
Rows are written through
:class:`~adapters.persistence.storage.SecureBoundRepository`, so
the namespace, schema version, and sensitivity declared by the storage registry
remain the persistence authority.

This module uses
:class:`~application.calculations._iva_compensation_history.IvaCompensationAnnualSummary`
and
:class:`~application.calculations._iva_compensation_history.IvaCompensationAnnualCrossCheck`
for Modelo 303-to-Modelo 390 annual cross-checking.

See Also:
    :mod:`domain.iva_compensation._carry_forward`
        Pure FIFO lot projection and four-year review policy.
    :mod:`application.calculations._iva_wallet_balance`
        Offline balance query built from this repository.
    :mod:`application.calculations._iva_wallet_reconciliation`
        Wallet/local-history reconciliation consumer for Modelo 303 prior
        compensation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    IVA_COMPENSATION_HISTORY_NAMESPACE,
    SecureBoundRepository,
    SensitivityClass,
    safe_repository_id,
)
from ...core import CasillaId, CasillaValueKind, IvaCompensationStateProvenance, Modelo, Period
from ...core.identity import AeatExpedienteId, ContentDigest, SubjectTaxId
from ...core.resources import bundled_path
from ...core.time import now
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.temporal import select_revision
from ...domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ...domain.iva_compensation import (
    IvaCompensationCarryForwardReport,
    IvaCompensationCasillaReferenceError,
    IvaCompensationDecimalParseError,
    IvaCompensationPeriodState,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
    derive_iva_compensation_year_end_carry_partition,
    iva_compensation_period_sort_key,
)
from .errors import IvaCompensationModeloError
from ._iva_compensation_casillas import (
    M303_COMPENSACION_APLICADA_CASILLA as _M303_COMPENSACION_APLICADA_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA as _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_DISPONIBLE_CASILLA as _M303_DISPONIBLE_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_GENERADA_CASILLA as _M303_GENERADA_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_POSTERIOR_CASILLA as _M303_POSTERIOR_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_RESULTADO_CASILLA as _M303_RESULTADO_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_RESULTADO_FINAL_CASILLA as _M303_RESULTADO_FINAL_CASILLA,
)
from ._iva_compensation_casillas import (
    M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA as _M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
)
from ._iva_compensation_casillas import (
    M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA as _M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA,
)
from ._observations_repository import CalculationObservationRepository, ObservationEnvelopePayload
from ._ports import FiledDeclaracionObservationProtocol

_ZERO = Decimal("0")


class IvaCompensationAnnualSummary(BaseModel):
    """Filed Modelo 390 annual IVA compensation summary for cross-checking.

    Compared against the
    :class:`~domain.iva_compensation._carry_forward.IvaCompensationCarryForwardReport`
    built from Modelo 303 period states by
    :func:`cross_check_iva_compensation_annual_summary`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    taxpayer_nif: SubjectTaxId = Field(
        description=(
            "The filing subject, validated through the canonical Spanish "
            "tax-identifier authority. The sibling "
            "IvaCompensationPeriodState already types this identity, and both "
            "are populated from the same authenticated_identity and compared "
            "against each other by the annual cross-check, so a bounded plain "
            "string here meant one side of that comparison ran the AEAT "
            "checksum and the other did not."
        ),
    )
    filing_year: int = Field(ge=2000, le=2099)
    expediente_id: AeatExpedienteId
    status: str = Field(min_length=1, max_length=32)
    presented_at: datetime
    last_period_compensation_amount: Decimal = Field(ge=_ZERO)
    generated_not_in_last_period_amount: Decimal = Field(ge=_ZERO)
    total_pending_amount: Decimal = Field(ge=_ZERO)
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


class IvaCompensationAnnualCrossCheck(BaseModel):
    """Comparison between Modelo 303 carry-forward lots and a filed Modelo 390 summary.

    Carries the expected Modelo 390 annual carry fields derived by
    :func:`~domain.iva_compensation._carry_forward.derive_iva_compensation_year_end_carry_partition`
    plus any mismatched
    ``CasillaId`` values.
    """

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
    """Encrypted profile-local store of Modelo 303 IVA compensation history.

    Persists
    :class:`~domain.iva_compensation._carry_forward.IvaCompensationPeriodState`
    rows in
    :data:`adapters.persistence.storage.IVA_COMPENSATION_HISTORY_NAMESPACE`
    for later carry-forward, balance, and reconciliation reads. The
    :class:`~adapters.persistence.storage.SecureBoundRepository` base
    writes those rows as encrypted AUDIT-class envelopes for active-bucket
    lookup.
    """

    namespace: ClassVar[str] = IVA_COMPENSATION_HISTORY_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_COMPENSATION_HISTORY_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_COMPENSATION_HISTORY_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = IvaCompensationPeriodState

    @override
    def extract_identifier(self, payload: IvaCompensationPeriodState) -> str:
        return iva_compensation_period_key(payload.period)

    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Return latest stored state for one period.

        Returns an
        :class:`~domain.iva_compensation._carry_forward.IvaCompensationPeriodState`
        when a record exists, or ``None`` when none has been persisted for the
        given period.
        """
        return self.load(iva_compensation_period_key(period))

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist latest stored state for one period."""
        self.save(state)

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Return stored :class:`~domain.iva_compensation._carry_forward.IvaCompensationPeriodState` rows.

        The returned tuple is sorted in chronological filing order using the
        same period sort key consumed by the domain carry-forward projection.
        """

        def _sort_key(item: IvaCompensationPeriodState) -> tuple[int, tuple[int, str]]:
            return (item.filing_year, iva_compensation_period_sort_key(item.period))

        return tuple(sorted(self.iter_records(), key=_sort_key))


_SEED_SOURCE_OBS_PREFIX = "303:seed"
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

    Returns an
    :class:`~domain.iva_compensation._carry_forward.IvaCompensationPeriodState`.

    Intended for first-time users whose historical M303 carry-forward pre-dates
    the local compensation history. The seeded state declares
    ``provenance=IvaCompensationStateProvenance.OPERATOR_SEED``; as a non-AEAT
    path, it carries ``status is None`` and no AEAT ``expediente_id``.

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
                "existing_provenance": existing.provenance.value,
            },
        )
    when = seeded_at if seeded_at is not None else now()
    state = IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
        filing_year=period.filing_year,
        period=period,
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

    Returns the corrected
    :class:`~domain.iva_compensation._carry_forward.IvaCompensationPeriodState`.

    The single-writer companion of :func:`seed_iva_compensation_period`: where
    seeding refuses if a record already exists, correction is the deliberate
    re-write path for a wrong opening compensation balance whose period
    pre-dates local history. It writes through the same
    :class:`~application.calculations._iva_compensation_history.IvaCompensationHistoryRepository`
    (no parallel write path), so the corrected state replaces the stored record
    at the same period key.

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
            context={
                "filing_year": period.filing_year,
                "period": period.registry_token,
                "existing_provenance": "absent",
            },
        )
    when = corrected_at if corrected_at is not None else now()
    state = IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION,
        filing_year=period.filing_year,
        period=period,
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


def iva_compensation_state_from_observation_envelope(
    envelope: ObservationEnvelopePayload,
    *,
    taxpayer_nif: str,
    provenance: IvaCompensationStateProvenance,
    expediente_id: str | None = None,
    status: str | None = None,
    source_observation_key: str,
    source_artefact_sha256: ContentDigest | None = None,
) -> IvaCompensationPeriodState:
    """Project one already-normalized M303 envelope into IVA history.

    The history boundary accepts no bare registry or filed observation. Those
    shapes omit the disposition that decides the available/generated pair, so
    treating either as history evidence would re-introduce an ungrounded carry
    default. The validator rejects legacy and mismatched envelopes before this
    constructor can select an amount.
    """
    from ._m303_carry_ingress import validate_normalized_m303_carry_observation_envelope

    validated = validate_normalized_m303_carry_observation_envelope(envelope)
    observation = validated.observation
    values = dict(observation.casilla_values)
    period = observation.filing_period or Period.from_year_and_code(observation.filing_year, observation.period)
    return IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        provenance=provenance,
        filing_year=observation.filing_year,
        period=period,
        expediente_id=expediente_id,
        status=status,
        presented_at=validated.captured_at,
        prior_pending_amount=_resolve_casilla_value(values, _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA),
        applied_amount=_resolve_casilla_value(values, _M303_COMPENSACION_APLICADA_CASILLA),
        pending_for_later_amount=_resolve_casilla_value(values, _M303_POSTERIOR_CASILLA),
        period_result_amount=_resolve_casilla_value(values, _M303_RESULTADO_CASILLA),
        final_result_amount=_resolve_casilla_value(values, _M303_RESULTADO_FINAL_CASILLA),
        generated_amount=values[_M303_GENERADA_CASILLA],
        available_end_amount=values[_M303_DISPONIBLE_CASILLA],
        source_observation_key=source_observation_key,
        source_artefact_sha256=source_artefact_sha256,
    )


def persist_observation_envelope_and_iva_history(
    *,
    observation_repository: CalculationObservationRepository,
    history_repository: IvaCompensationHistoryRepository,
    envelope: ObservationEnvelopePayload,
    taxpayer_nif: str,
    provenance: IvaCompensationStateProvenance,
    expediente_id: str | None = None,
    status: str | None = None,
    source_observation_key: str,
    source_artefact_sha256: ContentDigest | None = None,
) -> IvaCompensationPeriodState:
    """Atomically persist one M303 envelope and its history projection.

    The state is derived and its disposition-aware pair validated before either
    secure-object write is prepared. The two prepared writes then enter the
    shared backend's one transaction, so a refusal or a storage failure cannot
    leave an observation that history did not receive, or vice versa.
    """
    if history_repository.secure_object_repository is not observation_repository.secure_object_repository:
        from ._m303_carry_ingress import M303CarryIngressError

        raise M303CarryIngressError(
            translated_message="application.calculations.iva_compensation.errors.repository_backend_split",
            context={"taxpayer_nif_supplied": bool(taxpayer_nif)},
        )
    state = iva_compensation_state_from_observation_envelope(
        envelope,
        taxpayer_nif=taxpayer_nif,
        provenance=provenance,
        expediente_id=expediente_id,
        status=status,
        source_observation_key=source_observation_key,
        source_artefact_sha256=source_artefact_sha256,
    )
    observation_repository.secure_object_repository.apply_batch(
        (
            observation_repository.to_secure_object_write(envelope),
            history_repository.to_secure_object_write(state),
        ),
    )
    return state


def iva_compensation_annual_summary_from_filed_observation(
    observation: FiledDeclaracionObservationProtocol,
) -> IvaCompensationAnnualSummary:
    """Build an :class:`~application.calculations._iva_compensation_history.IvaCompensationAnnualSummary`.

    The source is a filed Modelo 390
    :class:`~application.calculations._ports.FiledDeclaracionObservationProtocol`.

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
    generated_not_in_last = (
        _resolve_casilla_value(
            values,
            _M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
        )
        or _ZERO
    )
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
    """Compare projections with filed evidence.

    Returns an
    :class:`~application.calculations._iva_compensation_history.IvaCompensationAnnualCrossCheck`.

    The expected ``iva.anual.compensacion-ultimo-periodo-97`` and
    ``iva.anual.compensacion-generada-ejercicio-no-97`` figures are derived
    through the SAME FIFO carry partition that drives the Modelo 390 calculation
    (:func:`~domain.iva_compensation._carry_forward.derive_iva_compensation_year_end_carry_partition`),
    so the
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


def _decimal_casilla_values(observation: FiledDeclaracionObservationProtocol) -> dict[CasillaId, Decimal]:
    _validate_observed_casilla_ids(observation)
    values: dict[CasillaId, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            continue
        # Modelo 303 and Modelo 390 declare only money casillas today, so this
        # refusal is unreachable on current registry data. It is not decoration:
        # these values feed cross-period IVA carry-forward balances, so the day a
        # revision adds a text casilla the refusal must already be here rather
        # than a wrong balance carried silently between filings.
        #
        # The kind is read through the port instead of catching what the accessor
        # raises, because that refusal is the adapter's exception type and this
        # layer does not import it.
        if casilla.value_kind is not CasillaValueKind.NUMERIC:
            raise _iva_compensation_decimal_refusal(observation, casilla.casilla_id)
        try:
            values[casilla.casilla_id] = casilla.decimal_value()
        except InvalidOperation as exc:
            raise _iva_compensation_decimal_refusal(observation, casilla.casilla_id) from exc
    return values


def _iva_compensation_decimal_refusal(
    observation: FiledDeclaracionObservationProtocol,
    casilla_id: CasillaId,
) -> IvaCompensationDecimalParseError:
    """Build the refusal for a casilla the carry-forward reader cannot read as an amount.

    Both Modelo 303 and Modelo 390 reach here, so the casilla id alone does not say
    which filing refused. Never add the observed VALUE to this context: the carrier
    holds the artefact's own token, and this context is rendered to the operator.
    """
    return IvaCompensationDecimalParseError(
        translated_message="errors.refused.refused_iva_compensation_decimal_parse",
        context={
            "casilla_id": casilla_id,
            "modelo": observation.modelo,
            "filing_year": str(observation.ejercicio),
            "period": observation.period.registry_token,
        },
    )


def _validate_observed_casilla_ids(observation: FiledDeclaracionObservationProtocol) -> None:
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(candidate for candidate in modelos if candidate.id == observation.modelo)
    revision = select_revision(
        modelo,
        filing_year=observation.ejercicio,
        period=observation.period.registry_token,
    )
    invalid = undeclared_casilla_ids(revision, (casilla.casilla_id for casilla in observation.casillas))
    if not invalid:
        return
    raise IvaCompensationCasillaReferenceError(
        context={
            "modelo": observation.modelo,
            "revision": revision.id,
            "period": observation.period.registry_token,
            "casilla_ids": invalid,
        },
        translated_message="application.calculations.iva_compensation.errors.observed_casilla_ids_noncanonical",
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
    "iva_compensation_state_from_observation_envelope",
    "persist_observation_envelope_and_iva_history",
    "seed_iva_compensation_period",
]
