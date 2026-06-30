"""Preparation gates for modelo calculation actions.

This module prepares calculation input channels against the registry
:class:`ModeloRevision` for a :class:`aeat.domain.modelos.WorkUnit`, resolves
the law-determined :class:`RegistrySnapshot`, applies the Modelo 303 IVA wallet
gate, and runs ledger preflight through a :class:`TransactionCatalogueRepository`
before calculation proceeds.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import replace as _dataclass_replace
from datetime import date
from decimal import Decimal

from ...core import Modelo
from ...domain.calculations.registry import BindingId, CasillaId, ModeloRevision, RelationId
from ...domain.deadlines import IVARegime
from ...domain.modelos._protocols import WorkUnitCatalogueRepositoryProtocol
from ...domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.period import period_end_date, period_start_date
from ...domain.transactions import (
    BusinessClassification,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ..calculations._observations_repository import IvaWalletDecisionRepository
from ..live import Borrador100SnapshotRepository
from . import _iva_wallet_gate
from ._action_errors import ModeloAggregationBindingError
from ._calculation_helpers import load_work_unit_for_calculation as _load_work_unit_for_calculation
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from ._calculation_resolution import ResolvedCalculationChannels
from ._calculation_resolution import resolve_calculation_binding_channels as _resolve_calculation_binding_channels
from ._registry_helpers import validate_casilla_input_ids as _validate_casilla_input_ids
from ._required_binding_gate import (
    require_modelo_required_bindings_resolved as _require_modelo_required_bindings_resolved,
)
from ._required_binding_gate import (
    resolved_required_profile_binding_values as _resolved_required_profile_binding_values,
)

_apply_iva_compensation_decision_binding = _iva_wallet_gate.apply_iva_compensation_decision_binding
_taxpayer_nif_for_bucket = _iva_wallet_gate.taxpayer_nif_for_bucket
resolve_iva_compensation_decision_for_calculation = _iva_wallet_gate.resolve_iva_compensation_decision_for_calculation


@dataclass(frozen=True, slots=True)
class PreparedCalculation:
    """Validated calculation preflight bundle consumed by the action layer.

    ``work_unit`` is the loaded :class:`aeat.domain.modelos.WorkUnit`;
    ``snapshot`` is the resolved :class:`RegistrySnapshot`; ``channels`` is the
    merged :class:`ResolvedCalculationChannels` set that the registry engine will
    consume. Casilla inputs have already been canonicalised and ledger, profile,
    required-binding, borrador, and IVA-wallet gates have already run.
    """

    work_units: WorkUnitCatalogue
    work_unit: WorkUnit
    snapshot: object
    casilla_inputs: Mapping[CasillaId, Decimal]
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None
    period_date: date
    channels: ResolvedCalculationChannels


def prepare_calculation(
    *,
    work_unit_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    ledger_preflight_transaction_repository: TransactionCatalogueRepository | None,
    iva_compensation_decision: object | None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None,
    binding_values: Mapping[BindingId, Decimal] | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    filing_period_date: date | None,
    borrador_snapshot_id: str | None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None,
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
) -> PreparedCalculation:
    """Prepare validated inputs, source channels, and gates for calculation.

    The resolved registry :class:`ModeloRevision` supplies binding and casilla
    requirements. ``ledger_preflight_transaction_repository`` may provide a
    :class:`TransactionCatalogueRepository` for the ledger-tax readiness check.
    ``iva_compensation_decision_repository`` may provide the matching
    :class:`aeat.application.calculations.IvaWalletDecisionRepository` for the
    Modelo 303 wallet authority, while
    :class:`aeat.application.live.Borrador100SnapshotRepository` supplies the
    optional Modelo 100 borrador tier.

    Returns:
        A :class:`PreparedCalculation` carrying the work unit, snapshot, validated
        inputs, period date, and resolved binding channels.
    """
    work_units = work_unit_repository.load()
    work_unit = _load_work_unit_for_calculation(work_units, work_unit_id=work_unit_id)
    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(work_unit)
    snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    casilla_inputs = _validate_casilla_input_ids(snapshot.revision, casilla_inputs)
    if backend_casilla_inputs is not None:
        backend_casilla_inputs = _validate_casilla_input_ids(snapshot.revision, backend_casilla_inputs)
    _raise_if_ledger_preflight_blocks_calculation(
        work_unit=work_unit,
        revision=snapshot.revision,
        transaction_repository=ledger_preflight_transaction_repository,
    )
    _raise_if_m200_ledger_requires_accounting_result_input(
        work_unit=work_unit,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        transaction_repository=ledger_preflight_transaction_repository,
    )
    iva_compensation_decision = resolve_iva_compensation_decision_for_calculation(
        work_unit,
        snapshot=snapshot,
        supplied_decision=iva_compensation_decision,
        repository=iva_compensation_decision_repository,
        binding_values=binding_values,
        backend_binding_values=backend_binding_values,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
    )
    period_date = filing_period_date or period_end_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period.registry_token,
    )
    caller_binding_values = dict(binding_values or {})
    caller_enum_binding_values = dict(enum_binding_values or {})
    lower_precedence_binding_values = dict(backend_binding_values or {})
    _apply_iva_compensation_decision_binding(
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        bucket_id=work_unit.bucket_id,
        revision=snapshot.revision,
        taxpayer_nif=_taxpayer_nif_for_bucket(work_unit.bucket_id),
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        caller_binding_values=caller_binding_values,
        backend_binding_values=lower_precedence_binding_values,
        decision=iva_compensation_decision,
    )
    channels = _resolve_calculation_binding_channels(
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_inputs=casilla_inputs,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        backend_binding_values=lower_precedence_binding_values,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=borrador_snapshot_repository,
    )
    required_profile_bindings = _resolved_required_profile_binding_values(
        work_unit=work_unit,
        registry_revision=snapshot.revision,
    )
    if required_profile_bindings:
        channels = _dataclass_replace(
            channels,
            bindings=dict(sorted({**required_profile_bindings, **channels.bindings}.items())),
        )
    _require_modelo_required_bindings_resolved(
        work_unit=work_unit,
        registry_revision=snapshot.revision,
        resolved_binding_ids=_resolved_binding_ids_for_required_binding_gate(
            revision=snapshot.revision,
            channels=channels,
            caller_binding_ids=caller_binding_values,
            unresolved_relation_ids=unresolved_relation_ids,
            unresolved_binding_ids=unresolved_binding_ids,
        ),
        action="calculate or save a draft",
    )
    return PreparedCalculation(
        work_units=work_units,
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        period_date=period_date,
        channels=channels,
    )


def _resolved_binding_ids_for_required_binding_gate(
    *,
    revision: ModeloRevision,
    channels: ResolvedCalculationChannels,
    caller_binding_ids: Mapping[BindingId, Decimal],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
) -> tuple[BindingId, ...]:
    resolved = set(channels.bindings) | set(channels.enum_bindings) | set(channels.date_bindings)
    caller_ids = set(caller_binding_ids)
    unresolved_relation_targets = {
        relation.target_binding
        for relation in revision.relations
        if relation.id in unresolved_relation_ids and relation.target_binding not in caller_ids
    }
    unresolved_bindings = set(unresolved_binding_ids).difference(caller_ids)
    return tuple(sorted(resolved.difference(unresolved_relation_targets).difference(unresolved_bindings)))


def _iva_regime_for_bucket(bucket_id: str) -> str | None:
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile._profile_repository import ProfileRepository
    from ..user_profile._projections import record_to_path_values

    try:
        profile = ProfileRepository().load(bucket_id)
        record = profile.record
    except ProfileNotFoundError:
        return None
    value = record_to_path_values(record).get("iva.regime")
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


_LEDGER_PREFLIGHT_BINDING_SOURCES = frozenset(
    {
        "ledger_iva_aggregation",
        "ledger_renta_expense_aggregation",
    },
)
_IVA_LEDGER_EXEMPT_REGIMES = frozenset({IVARegime.SIMPLIFICADO})
_M200_ACCOUNTING_RESULT_CASILLA: CasillaId = "00501"
_M200_ACCOUNTING_LEDGER_CLASSIFICATIONS = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    },
)
_M200_ACCOUNTING_LEDGER_DIRECTIONS = frozenset(
    {
        TransactionDirection.INCOMING,
        TransactionDirection.OUTGOING,
    },
)


def _raise_if_ledger_preflight_blocks_calculation(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> None:
    """Refuse ledger-backed calculations whose period ledger readiness blocks."""
    if not any(binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES for binding in revision.bindings):
        return
    iva_regime = _iva_regime_for_bucket(work_unit.bucket_id)
    if iva_regime in _IVA_LEDGER_EXEMPT_REGIMES:
        return
    from ..ledger import preflight_ledger_tax_readiness

    report = preflight_ledger_tax_readiness(
        bucket_id=work_unit.bucket_id,
        period=work_unit.period,
        transaction_repository=transaction_repository,
    )
    if report.ready:
        return
    first_issue = report.issues[0]
    raise ModeloAggregationBindingError(
        translated_message="application.modelo.errors.ledger_preflight_blocked",
        context={
            "transaction_id": first_issue.transaction_id,
            "reason": first_issue.reason.value,
            "detail": first_issue.detail,
            "period": str(report.period),
        },
        suggestion=f"aeat app ledger preflight --period {report.period.registry_token} --year {report.period.year}",
    )


def _raise_if_m200_ledger_requires_accounting_result_input(
    *,
    work_unit: WorkUnit,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    transaction_repository: TransactionCatalogueRepository | None,
) -> None:
    """Refuse Modelo 200 ledger-backed calculation without accounting-result input."""
    if str(work_unit.modelo) != Modelo.M200.value:
        return
    if _M200_ACCOUNTING_RESULT_CASILLA in casilla_inputs or (
        backend_casilla_inputs is not None and _M200_ACCOUNTING_RESULT_CASILLA in backend_casilla_inputs
    ):
        return
    ledger_transaction_count = _m200_accounting_ledger_transaction_count(
        work_unit=work_unit,
        transaction_repository=transaction_repository,
    )
    if ledger_transaction_count == 0:
        return
    period_label = f"{work_unit.filing_year}/{work_unit.period.registry_token}"
    raise ModeloAggregationBindingError(
        (
            "Modelo 200 does not derive accounting profit from ledger transactions yet; "
            f"the bucket has {ledger_transaction_count} business ledger row(s) in {period_label}. "
            "Supply casilla 00501 from the company's accounting result before calculating."
        ),
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "ledger_transaction_count": ledger_transaction_count,
            "required_casilla_id": _M200_ACCOUNTING_RESULT_CASILLA,
        },
        suggestion=(
            f"aeat app modelo work calculate {work_unit.work_unit_id} "
            f"--casilla {_M200_ACCOUNTING_RESULT_CASILLA}=<resultado-contable>"
        ),
    )


def _m200_accounting_ledger_transaction_count(
    *,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
) -> int:
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    period_start = period_start_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period.registry_token,
    )
    period_end = period_end_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period.registry_token,
    )
    count = 0
    for transaction in repository.load():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.direction not in _M200_ACCOUNTING_LEDGER_DIRECTIONS:
            continue
        if transaction.business_classification not in _M200_ACCOUNTING_LEDGER_CLASSIFICATIONS:
            continue
        effective_date = transaction.raw.value_date or transaction.raw.booked_date
        if period_start <= effective_date <= period_end:
            count += 1
    return count
