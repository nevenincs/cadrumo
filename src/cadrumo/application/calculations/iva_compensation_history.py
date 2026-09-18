"""Profile-scoped IVA compensation history built from filed Modelo 303s.

This module owns the application policy and typed state projections.  A required
application capability persists the state; encrypted storage and its failure
modes are bound outside this module.

See Also:
    :mod:`domain.iva_compensation.carry_forward`
        Pure FIFO lot projection and four-year review policy.
    :mod:`application.calculations.iva_wallet_balance`
        Offline balance query built from this repository.
    :mod:`application.calculations.iva_wallet_reconciliation`
        Wallet/local-history reconciliation consumer for Modelo 303 prior
        compensation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.decimal.constants import ZERO
from ...core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ...core.identity.digest import ContentDigest
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_APLICADA_CASILLA as _M303_COMPENSACION_APLICADA_CASILLA,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_AVAILABLE_CASILLA as _M303_DISPONIBLE_CASILLA,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_GENERADA_CASILLA as _M303_GENERADA_CASILLA,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_PENDING_PRIOR_CASILLA as _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_POSTERIOR_CASILLA as _M303_POSTERIOR_CASILLA,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA as _M303_RESULTADO_CASILLA,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_FINAL_CASILLA as _M303_RESULTADO_FINAL_CASILLA,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.iva_compensation.carry_forward import (
    IvaCompensationPeriodState,
)
from ...domain.iva_compensation.errors import (
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)
from .errors import IvaCompensationModeloError
from .iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from .observations_repository import CalculationObservationRepositoryProtocol, ObservationEnvelopePayload
from .revision_carry_gate import revision_carry_outcome


def iva_compensation_period_key(period: Period) -> str:
    """Return the latest-state key for one Modelo 303 period."""
    filing_year = period.filing_year
    if not FILING_YEAR_MIN <= filing_year <= FILING_YEAR_MAX:
        raise IvaCompensationYearRangeError(
            translated_message="errors.refused.refused_iva_compensation_year_range",
            context={"filing_year": filing_year, "min_year": FILING_YEAR_MIN, "max_year": FILING_YEAR_MAX},
        )
    return f"303:{filing_year}:{period.registry_token}"


def require_iva_compensation_period_coordinates_current(
    state: IvaCompensationPeriodState,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse persisted compensation state whose registry coordinate is stale."""
    outcome = revision_carry_outcome(state.registry_snapshot_ref, operation=operation)
    if outcome.refused:
        raise IvaCompensationModeloError(
            "persisted IVA compensation period state registry coordinate cannot be re-confirmed: "
            f"{state.registry_snapshot_ref.revision_id}: {outcome.detail}"
        )


_SEED_SOURCE_OBS_PREFIX = "303:seed"
_CORRECTED_SOURCE_OBS_PREFIX = "303:correction"


def _registry_snapshot_ref_for_m303_period(
    period: Period,
    *,
    operation: PinnedAuthorityOperation,
) -> RegistrySnapshotRef:
    revision = operation.revision_for_context(
        Modelo("303").value,
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    return RegistrySnapshotRef(
        modelo=Modelo("303").value,
        revision_id=str(revision.id),
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


def seed_iva_compensation_period(
    *,
    taxpayer_nif: str,
    period: Period,
    amount: Decimal,
    repository: IvaCompensationHistoryRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    seeded_at: datetime | None = None,
) -> IvaCompensationPeriodState:
    """Persist a manually declared carry-forward balance for one Modelo 303 period.

    Returns an
    :class:`~domain.iva_compensation.carry_forward.IvaCompensationPeriodState`.

    Intended for first-time users whose historical M303 carry-forward pre-dates
    the local compensation history. The seeded state declares
    ``provenance=IvaCompensationStateProvenance.OPERATOR_SEED``; as a non-AEAT
    path, it carries ``status is None`` and no AEAT ``expediente_id``.

    Raises ``IvaCompensationSeedConflictError`` if a state already exists for
    the specified period — seeding must not overwrite an existing record.
    """
    existing = repository.load_period(period)
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
        registry_snapshot_ref=_registry_snapshot_ref_for_m303_period(period, operation=operation),
        presented_at=when,
        prior_pending_amount=None,
        applied_amount=None,
        pending_for_later_amount=amount,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=ZERO,
        available_end_amount=amount,
        source_observation_key=f"{_SEED_SOURCE_OBS_PREFIX}:{period.filing_year}:{period.registry_token}",
        source_artefact_sha256=None,
    )
    repository.save_period(state)
    return state


def correct_iva_compensation_period(
    *,
    taxpayer_nif: str,
    period: Period,
    amount: Decimal,
    repository: IvaCompensationHistoryRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    corrected_at: datetime | None = None,
) -> IvaCompensationPeriodState:
    """Overwrite a manually-seeded carry-forward balance for one Modelo 303 period.

    Returns the corrected
    :class:`~domain.iva_compensation.carry_forward.IvaCompensationPeriodState`.

    The single-writer companion of :func:`seed_iva_compensation_period`: where
    seeding refuses if a record already exists, correction is the deliberate
    re-write path for a wrong opening compensation balance whose period
    pre-dates local history. It writes through the same
    :class:`IvaCompensationHistoryRepositoryProtocol`
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
    existing = repository.load_period(period)
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
        registry_snapshot_ref=_registry_snapshot_ref_for_m303_period(period, operation=operation),
        presented_at=when,
        prior_pending_amount=None,
        applied_amount=None,
        pending_for_later_amount=amount,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=ZERO,
        available_end_amount=amount,
        source_observation_key=f"{_CORRECTED_SOURCE_OBS_PREFIX}:{period.filing_year}:{period.registry_token}",
        source_artefact_sha256=None,
    )
    repository.save_period(state)
    return state


def iva_compensation_state_from_observation_envelope(
    envelope: ObservationEnvelopePayload,
    *,
    taxpayer_nif: str,
    provenance: IvaCompensationStateProvenance,
    expediente_id: str | None = None,
    status: str | None = None,
    source_observation_key: str,
    operation: PinnedAuthorityOperation,
    source_artefact_sha256: ContentDigest | None = None,
) -> IvaCompensationPeriodState:
    """Project one already-normalized M303 envelope into IVA history.

    The history boundary accepts no bare registry or filed observation. Those
    shapes omit the disposition that decides the available/generated pair, so
    treating either as history evidence would re-introduce an ungrounded carry
    default. The validator rejects legacy and mismatched envelopes before this
    constructor can select an amount.
    """
    from .m303_carry_ingress import validate_normalized_m303_carry_observation_envelope

    validated = validate_normalized_m303_carry_observation_envelope(envelope, operation=operation)
    observation = validated.observation
    values = dict(observation.casilla_values)
    period = observation.filing_period or Period.from_year_and_code(observation.filing_year, observation.period)
    return IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        provenance=provenance,
        filing_year=observation.filing_year,
        period=period,
        registry_snapshot_ref=validated.registry_snapshot_ref,
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
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    envelope: ObservationEnvelopePayload,
    taxpayer_nif: str,
    provenance: IvaCompensationStateProvenance,
    expediente_id: str | None = None,
    status: str | None = None,
    source_observation_key: str,
    operation: PinnedAuthorityOperation,
    source_artefact_sha256: ContentDigest | None = None,
) -> IvaCompensationPeriodState:
    """Atomically persist one M303 envelope and its history projection.

    The state is derived and its disposition-aware pair validated before either
    secure-object write is prepared. The two prepared writes then enter the
    shared backend's one transaction, so a refusal or a storage failure cannot
    leave an observation that history did not receive, or vice versa.
    """
    if history_repository.secure_object_repository is not observation_repository.secure_object_repository:
        from .m303_carry_ingress import M303CarryIngressError

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
        operation=operation,
        source_artefact_sha256=source_artefact_sha256,
    )
    observation_repository.secure_object_repository.apply_batch(
        (
            observation_repository.to_secure_object_write(envelope),
            history_repository.to_secure_object_write(state),
        ),
    )
    return state


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
    "correct_iva_compensation_period",
    "iva_compensation_period_key",
    "iva_compensation_state_from_observation_envelope",
    "persist_observation_envelope_and_iva_history",
    "require_iva_compensation_period_coordinates_current",
    "seed_iva_compensation_period",
]
