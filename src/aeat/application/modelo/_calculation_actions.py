"""Calculation revision actions for modelo work units.

The calculate paths resolve a law-determined :class:`RegistrySnapshot` from
each :class:`aeat.domain.modelos.WorkUnit`, merge manual inputs with profile,
borrador, IVA-wallet, and bucket aggregation channels, and execute
:func:`aeat.domain.calculations.registry.calculate_registry_snapshot` against
the asserted :class:`ModeloRevision`.

Persistence is centralized through :class:`CalculationRevision`,
:class:`aeat.domain.modelos.CalculationRevisionCatalogueRepository`,
and :class:`BucketEventHistoryRepository`, so the work-unit pointer and
``modelo.calculation.created`` event advance with the stored draft revision.

``calculate_modelo_revision`` is the lower-level calculation service: callers
provide already-resolved manual, binding, enum-binding, relation, borrador, and
IVA-wallet inputs. ``calculate_modelo_revision_from_bucket_aggregation`` first
runs the application source mesh over bucket-local ledgers, invoices, previous
filings, relation prefill, retenciones, withholding, and detail rows, then feeds
the resolved backend channels into the same persistence path. Source-owned
bindings and their bound casillas are guarded before the engine runs so a
persisted revision cannot claim bucket-source grounding while carrying a caller
substitute for the same value.

See Also:
    :mod:`aeat.application.aggregation`:
        Public source-mesh contracts and diagnostics consumed by the bucket
        aggregation path.
    :func:`aeat.application.modelo._calculation_resolution.resolve_calculation_binding_channels`:
        Merges caller, backend, borrador, and date binding channels for the
        registry engine.
    :func:`aeat.application.modelo._calculation_helpers.build_typed_observations`:
        Projects engine output into provenance-bearing casilla observations.
    :func:`aeat.application.modelo._revision_persistence.persist_calculation_revision`:
        Stores the content-addressed ``BORRADOR`` revision and emits the bucket
        event.
    :func:`aeat.application.modelo._verification_actions.verify_modelo_revision`:
        Lifecycle gate that promotes a calculated revision after verification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core import BindingSourceKind, Modelo
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepository
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    CasillaObservation,
    InputKind,
    ModeloRevision,
    RelationId,
    bound_casilla_binding_ids,
    calculate_registry_snapshot,
    casillas_by_id,
    relation_source_requirements,
)
from ...domain.invoices import InvoiceCatalogueRepository
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._row_models import Modelo349OperadorRow, ModeloDetailRow
from ...domain.modelos._work_unit import WorkUnit
from ...domain.transactions import TransactionCatalogueRepository
from ..calculations import cross_period_dependency_requirements as _cross_period_dependency_requirements
from ..live import Borrador100SnapshotRepository
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloAggregationBindingError,
    ModeloCrossPeriodCleanStateError,
    WorkUnitNotFoundError,
)
from ._binding_resolution import (
    resolve_available_bound_inputs_by_casilla_id,
)
from ._calculation_aggregation_context import load_bucket_aggregation_context as _load_bucket_aggregation_context
from ._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from ._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)
from ._calculation_helpers import (
    resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit,
)
from ._calculation_preparation import _IVA_LEDGER_EXEMPT_REGIMES as _IVA_LEDGER_EXEMPT_REGIMES
from ._calculation_preparation import (
    _raise_if_ledger_preflight_blocks_calculation as _raise_if_ledger_preflight_blocks_calculation,
)
from ._calculation_preparation import prepare_calculation as _prepare_calculation
from ._calculation_resolution import (
    build_calculation_replay_payloads as _build_calculation_replay_payloads,
)
from ._calculation_resolution import (
    resolve_calculation_inputs as _resolve_calculation_inputs,
)
from ._calculation_source_policy import (
    _BINDING_SOURCE_DISPOSITIONS as _BINDING_SOURCE_DISPOSITIONS,
)
from ._calculation_source_policy import (
    _ENROLLED_SOURCE_KINDS as _ENROLLED_SOURCE_KINDS,
)
from ._calculation_source_policy import (
    ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS,
    BUCKET_AGGREGATION_LOCK_SOURCES,
    BUCKET_AGGREGATION_OWNED_SOURCES,
    CALLER_OVERRIDABLE_CARRY_SOURCES,
)
from ._m349_ledger_guard import (
    raise_if_m349_intracom_ledger_rows_need_operator_rows as _raise_if_m349_intracom_ledger_rows_need_operator_rows,
)
from ._registry_helpers import validate_casilla_input_ids as _validate_casilla_input_ids
from ._revision_persistence import persist_calculation_revision

if TYPE_CHECKING:
    from ...domain.calculations.registry import RegistrySnapshot
    from ..aggregation import CalculationSourceDiagnostic, CalculationSourceResolution
    from ..calculations._observations_repository import IvaWalletDecisionRepository


@dataclass(frozen=True, slots=True)
class BucketAggregationCalculationResult:
    """Calculation revision plus the non-blocking source diagnostics raised while resolving it.

    ``revision`` is the persisted :class:`CalculationRevision`.
    ``source_diagnostics`` carries the
    :class:`aeat.application.aggregation.CalculationSourceDiagnostic` rows the
    source mesh emitted during resolution, notably the unconsumed-declarable-IVA
    advisories (a declarable IVA observation no ``ledger_iva_aggregation``
    binding selects). They are NON-blocking: the revision was computed and
    persisted regardless. Surfacing them keeps an unrouted declarable
    observation from being silently under-declared (no-silent-under-declaration).
    """

    revision: CalculationRevision
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


_M349_NUMERO_OPERADORES_BINDING: BindingId = "iva-349-declarante-numero-operadores"
_M349_IMPORTE_OPERACIONES_BINDING: BindingId = "iva-349-declarante-importe-operaciones"
_M349_NUMERO_RECTIFICACIONES_BINDING: BindingId = "iva-349-declarante-numero-rectificaciones"
_M349_IMPORTE_RECTIFICACIONES_BINDING: BindingId = "iva-349-declarante-importe-rectificaciones"
_BUCKET_AGGREGATION_OWNED_SOURCES = BUCKET_AGGREGATION_OWNED_SOURCES
_ZERO = Decimal("0")
_M390_ANNUAL_PERIOD_CODE = "0A"
_M390_303_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE: Mapping[CasillaId, CasillaId] = {
    "iva.cuota-devengada-total": "iva.anual.cuota-devengada-total",
    "iva.cuota-deducible-total": "iva.anual.cuota-deducible-total",
    "iva.resultado-regimen-general": "iva.anual.resultado-regimen-general",
}


def _m349_row_field_template_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    return frozenset(
        casilla_id
        for export_layout in revision.export_layouts
        for record in export_layout.records
        for casilla_id in record.row_field_casilla_ids.values()
    )


def _calculated_decimal(value: object | None) -> Decimal:
    if value is None:
        return _ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _m390_303_reconciliation_targets(
    snapshot: RegistrySnapshot,
) -> tuple[tuple[RelationId, BindingId, CasillaId, CasillaId, CasillaId], ...]:
    """Return M390 reconciliation relation targets keyed by their M303 source output."""
    target_casillas_by_binding = {
        casilla.binding: casilla.id for casilla in snapshot.revision.casillas if casilla.binding is not None
    }
    targets: list[tuple[RelationId, BindingId, CasillaId, CasillaId, CasillaId]] = []
    for relation in snapshot.revision.relations:
        if relation.source_modelo != Modelo.M303.value:
            continue
        annual_casilla = _M390_303_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE.get(relation.source_casilla_id)
        if annual_casilla is None:
            continue
        target_casilla = target_casillas_by_binding.get(relation.target_binding)
        if target_casilla is None:
            continue
        targets.append(
            (
                relation.id,
                relation.target_binding,
                target_casilla,
                relation.source_casilla_id,
                annual_casilla,
            ),
        )
    return tuple(targets)


def _m390_303_required_periods(snapshot: RegistrySnapshot, relation_ids: frozenset[RelationId]) -> tuple[str, ...]:
    periods: set[str] = set()
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if relation_ids.intersection(requirement.relation_ids):
            periods.update(requirement.periods)
    return tuple(sorted(periods))


def _raise_if_m390_303_reconciliation_would_save_silent_zero(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    resolved_binding_values: Mapping[BindingId, Decimal],
) -> None:
    """Refuse an M390 draft that would save zero 303 reconciliation slots from missing fold-in evidence."""
    if str(work_unit.modelo) != Modelo.M390.value or work_unit.period.registry_token != _M390_ANNUAL_PERIOD_CODE:
        return

    missing: list[tuple[RelationId, BindingId, CasillaId, CasillaId]] = []
    for relation_id, binding_id, target_casilla, _source_casilla, annual_casilla in _m390_303_reconciliation_targets(
        snapshot,
    ):
        if binding_id in resolved_binding_values:
            continue
        if _calculated_decimal(casilla_values.get(annual_casilla)) == _ZERO:
            continue
        missing.append((relation_id, binding_id, target_casilla, annual_casilla))

    if not missing:
        return

    missing_relation_ids = frozenset(relation_id for relation_id, _binding_id, _target, _annual in missing)
    raise ModeloCrossPeriodCleanStateError(
        (
            "Modelo 390 calculation refused: nonzero annual IVA totals are present, "
            "but the Modelo 303 reconciliation bindings did not resolve from clean "
            "current quarterly filing observations."
        ),
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": len(missing),
            "reason": "missing_clean_cross_period_303_filings_or_observations",
            "missing_303_periods": _m390_303_required_periods(snapshot, missing_relation_ids),
            "missing_303_reconciliation_bindings": tuple(binding_id for _rel, binding_id, _target, _annual in missing),
            "zero_reconciliation_casillas_at_risk": tuple(target for _rel, _binding, target, _annual in missing),
            "nonzero_annual_casillas": tuple(annual for _rel, _binding, _target, annual in missing),
        },
        suggestion="aeat app live filed pull-sources --modelo 303",
    )


def _suppress_m349_row_field_template_outputs(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    casilla_values: dict[CasillaId, Decimal],
    observations: tuple[CasillaObservation, ...],
) -> tuple[dict[CasillaId, Decimal], tuple[CasillaObservation, ...]]:
    if str(work_unit.modelo) != Modelo.M349.value:
        return casilla_values, observations
    row_field_casilla_ids = _m349_row_field_template_casilla_ids(revision)
    if not row_field_casilla_ids:
        return casilla_values, observations
    return (
        {casilla_id: value for casilla_id, value in casilla_values.items() if casilla_id not in row_field_casilla_ids},
        tuple(observation for observation in observations if observation.casilla_id not in row_field_casilla_ids),
    )


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    ledger_preflight_transaction_repository: TransactionCatalogueRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    source_transaction_ids: tuple[str, ...] = (),
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Run the registry formula engine, persist a draft revision, and return a :class:`CalculationRevision`.

    ``ledger_preflight_transaction_repository`` is a :class:`TransactionCatalogueRepository`
    used for the ledger preflight check before calculation.

    Pipeline:

    1. Load the work unit; refuse on DISCARDED.
    2. Resolve the :class:`RegistrySnapshot` for the work unit's
       ``(modelo, filing_year, period)`` and assert its
       :class:`ModeloRevision`. Failure to resolve raises
       :exc:`CalculationRegistryUnavailableError` — the calculate
       path runs the engine, so a missing snapshot is a hard refusal.
    3. Run :func:`aeat.domain.calculations.registry.calculate_registry_snapshot`
       over the snapshot
       with the operator-supplied manual casilla inputs, binding
       values, enum-binding values, and relation values. The
       engine evaluates every declared formula in dependency order
       and returns the full ``casilla_values`` map (inputs plus
       formula outputs).
    4. Build canonical replay payloads for inputs, binding overrides,
       enum/date bindings, and relation overrides (so the content-addressed
       revision id is stable across structurally identical re-runs).
    5. Project the engine result to :class:`CasillaObservation` rows and persist
       the revision in ``BORRADOR`` state; advance the work unit's
       ``current_calculation_revision_id`` pointer; emit
       ``modelo.calculation.created``.

    The revision starts in ``BORRADOR`` state; callers must run
    :func:`aeat.application.modelo.verify_modelo_revision` and
    :func:`aeat.application.modelo.file_modelo_revision`
    explicitly to advance through the lifecycle.

    See Also:
        :func:`aeat.application.modelo._calculation_resolution.build_calculation_replay_payloads`:
            Canonicalizes the values that participate in the revision id.
        :func:`aeat.application.modelo._calculation_helpers.build_typed_observations`:
            Carries registry legal/source provenance onto the persisted
            revision.
        :func:`aeat.application.modelo._revision_persistence.persist_calculation_revision`:
            Owns duplicate detection, work-unit pointer advancement, and event
            emission.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    prepared = _prepare_calculation(
        work_unit_id=work_unit_id,
        work_unit_repository=wu_repo,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        ledger_preflight_transaction_repository=ledger_preflight_transaction_repository,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        backend_binding_values=backend_binding_values,
        filing_period_date=filing_period_date,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=borrador_snapshot_repository,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
    )
    work_units = prepared.work_units
    work_unit = prepared.work_unit
    snapshot = prepared.snapshot
    resolved_relations = dict(relation_values or {})
    resolved_inputs = _resolve_calculation_inputs(
        revision=snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        backend_casilla_inputs=prepared.backend_casilla_inputs,
        resolved_bindings=prepared.channels.bindings,
        casilla_inputs=prepared.casilla_inputs,
    )

    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=resolved_inputs,
        date_context={"filing_period": prepared.period_date},
        binding_values=prepared.channels.bindings,
        enum_binding_values=prepared.channels.enum_bindings,
        relation_values=resolved_relations,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        date_binding_values=prepared.channels.date_bindings or None,
    )

    replay_payloads = _build_calculation_replay_payloads(
        resolved_inputs=resolved_inputs,
        resolved_bindings=prepared.channels.bindings,
        resolved_enum_bindings=prepared.channels.enum_bindings,
        resolved_date_bindings=prepared.channels.date_bindings,
        resolved_relations=resolved_relations,
    )
    casilla_values = dict(engine_result.values)
    _raise_if_m390_303_reconciliation_would_save_silent_zero(
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_values=casilla_values,
        resolved_binding_values=prepared.channels.bindings,
    )
    typed_observations = _build_typed_observations(engine_result=engine_result, snapshot=snapshot)
    casilla_values, typed_observations = _suppress_m349_row_field_template_outputs(
        work_unit=work_unit,
        revision=snapshot.revision,
        casilla_values=casilla_values,
        observations=typed_observations,
    )

    now = clock or _utc_now()
    return persist_calculation_revision(
        work_unit_id=work_unit_id,
        work_unit=work_unit,
        work_units=work_units,
        input_values_by_casilla_id=replay_payloads.input_values_by_casilla_id,
        binding_overrides=replay_payloads.binding_overrides,
        relation_overrides=replay_payloads.relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=prepared.channels.borrador_snapshot_id,
        bindings_sourced_from_borrador=prepared.channels.bindings_sourced_from_borrador,
        observations=typed_observations,
        detail_rows=detail_rows,
        formula_count=len(engine_result.entries),
        actor=actor,
        now=now,
        calculation_repository=cr_repo,
        work_unit_repository=wu_repo,
        bucket_event_repository=bv_repo,
    )


def calculate_modelo_revision_from_bucket_aggregation(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Calculate a modelo revision through the bucket-local source mesh.

    ``transaction_repository`` is a :class:`TransactionCatalogueRepository` used to
    load bucket-local ledger transactions for aggregation.
    ``invoice_repository`` is an :class:`InvoiceCatalogueRepository` used by
    invoice and OSS/IOSS resolvers. The wrapper resolves enrolled source
    families into backend binding, casilla, relation, detail-row, and provenance
    channels, rejects caller collisions with source-owned bindings, and then
    delegates to :func:`aeat.application.modelo.calculate_modelo_revision`.

    Returns a :class:`CalculationRevision`. Use
    :func:`aeat.application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
    when the caller also needs the non-blocking source diagnostics (e.g. the
    operator-facing CLI calculate surface, which surfaces unconsumed-declarable
    IVA advisories).

    See Also:
        :func:`_resolve_bucket_source_mesh`:
            Runs the enrolled resolver set and returns the merged
            :class:`aeat.application.aggregation.CalculationSourceResolution`.
        :func:`_reject_caller_overrides_of_source_bindings`:
            Refuses caller values for source-owned binding and bound-casilla
            slots.
    """
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=detail_rows,
        clock=clock,
    ).revision


def _resolve_bucket_source_mesh(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    transaction_repository: TransactionCatalogueRepository | None,
    invoice_repository: InvoiceCatalogueRepository | None,
) -> CalculationSourceResolution:
    """Resolve the live source mesh for a bucket-aggregation calculation.

    Builds the :class:`aeat.application.aggregation.CalculationSourceContext`,
    runs every enrolled ledger / invoice / carry resolver through
    :func:`aeat.application.aggregation.merge_source_resolutions`, and augments
    the result with the unhandled-binding-source advisories for any declared
    source with no enrolled resolver. Returns the merged
    :class:`aeat.application.aggregation.CalculationSourceResolution`.
    """
    from ..aggregation import (
        CalculationSourceContext,
        CalculationSourceDiagnostic,
        LedgerIvaAggregationSourceResolver,
        LedgerRentaExpenseAggregationSourceResolver,
        LedgerRentaGastoAggregationSourceResolver,
        LedgerRentaIncomeAggregationSourceResolver,
        OssIossLedgerSourceResolver,
        RetencionesAggregationSourceResolver,
        WithholdingSourceResolver,
        collect_unhandled_source_diagnostics,
        merge_source_resolutions,
    )
    from ..calculations import (
        IvaCompensationAnnualPartitionSourceResolver,
        PreviousFilingSourceResolver,
        RelationPrefillSourceResolver,
    )
    from ..invoices import InvoiceCatalogueSourceResolver

    context = CalculationSourceContext(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        revision=snapshot.revision,
    )
    source_resolution = merge_source_resolutions(
        (
            LedgerIvaAggregationSourceResolver(transaction_repository=transaction_repository).resolve(context),
            LedgerRentaExpenseAggregationSourceResolver(
                transaction_repository=transaction_repository,
                invoice_repository=invoice_repository,
            ).resolve(context),
            # M130 actividad-económica income (ledger_renta_income_aggregation).
            LedgerRentaIncomeAggregationSourceResolver(
                transaction_repository=transaction_repository,
            ).resolve(context),
            # M130 deductible-expense / gasto into casilla 02
            # (ledger_renta_gasto_aggregation) — the OUTGOING sibling of the
            # income resolver, same cumulative quarterly window.
            LedgerRentaGastoAggregationSourceResolver(
                transaction_repository=transaction_repository,
            ).resolve(context),
            # M369 OSS/IOSS (ledger_oss_aggregation).  The live path projects
            # OSS/IOSS-tagged issued invoices into validated ledger candidates;
            # pre-classified callers can still pass candidates directly through
            # the resolver constructor.
            OssIossLedgerSourceResolver(invoice_repository=invoice_repository).resolve(context),
            # Retenciones family source (retenciones_aggregation): M115 reads the
            # dedicated per-perceptor store for quarterly count/base, while M180/M193
            # read it for distinct perceptor-NIF counts. Empty store on a declaring
            # revision surfaces a no-silent advisory.
            RetencionesAggregationSourceResolver().resolve(context),
            # M190 distinct percepción count (withholding): reads the dedicated
            # per-perceptor-clave withholding store and materialises scalar
            # withholding bindings. Empty store on a declaring revision surfaces
            # a no-silent advisory while still materialising an explicit zero.
            WithholdingSourceResolver().resolve(context),
            # M349 collectible / payable invoices (collectible_invoice,
            # payable_invoice).  Loads the encrypted invoice catalogue and resolves
            # binding values for intra-community transactions in scope.
            InvoiceCatalogueSourceResolver(
                invoice_repository=invoice_repository,
            ).resolve(context),
            # Cross-period carry: prior-filing observations flow through the
            # backend-binding channel so an automatically-carried previous_filing
            # value fills the binding gap, while a caller --binding still
            # overrides it (it is deliberately NOT added to the owned-source
            # rejection set below — ruling D2). The 303 IVA-compensation
            # binding is excluded here because the iva-wallet compensación
            # decision owns it (ruling D3).
            _previous_filing_resolution_excluding_iva_compensation(
                PreviousFilingSourceResolver(
                    registry_snapshot=snapshot,
                    excluded_binding_ids=_iva_compensation_previous_filing_exclusions(),
                ).resolve(context),
            ),
            # Relation canonical for cross-modelo fold-in. The relation resolver
            # folds prior filed observations through each declared relation's
            # aggregation op and MATERIALISES the result into the relation's
            # target_binding slot (now declared source = "relation_prefill"). The
            # materialised binding values ride in this resolution's binding_values
            # so the mesh _claim_binding exclusive-ownership guard adjudicates any
            # collision loudly (aggregation-taxonomy rulings 2+4). This brings the
            # entire relation corpus (M100 pagos-fraccionados + retenciones
            # credits, M180/M190/M193 reconciliations, M200/M202 carries) live on
            # the operator calculate path.
            RelationPrefillSourceResolver(registry_snapshot=snapshot).resolve(context),
            # Modelo 390 annual compensation carry boxes 97 / 662 are one FIFO
            # partition over filed Modelo 303 compensation states, not two
            # independent relation copy/sum folds.
            IvaCompensationAnnualPartitionSourceResolver(registry_snapshot=snapshot).resolve(context),
        ),
    )
    source_resolution = _source_resolution_excluding_iva_compensation(snapshot.revision, source_resolution)
    # Safety net: collect non-blocking advisories for every binding whose declared
    # source has no enrolled resolver and is not explicitly deferred.
    # handled_sources covers all enrolled-resolver owned_sources plus the three
    # pre-mesh-handled source kinds (profile, borrador, iva_wallet_decision).
    # DEFERRED_SOURCE_KINDS are NOT on the manual_sources allowlist so they still
    # emit an advisory.
    _pre_mesh_handled: frozenset[BindingSourceKind] = frozenset(
        {
            BindingSourceKind.PROFILE,
            BindingSourceKind.BORRADOR,
            BindingSourceKind.IVA_WALLET_DECISION,
        },
    )
    _handled = frozenset(source_resolution.owned_sources) | _pre_mesh_handled
    _unhandled_diagnostics = collect_unhandled_source_diagnostics(
        snapshot.revision,
        handled_sources=_handled,
        manual_sources=frozenset({"manual_input"}),
    )
    if _unhandled_diagnostics:
        source_resolution = source_resolution.model_copy(
            update={"diagnostics": source_resolution.diagnostics + _unhandled_diagnostics},
        )
    # Expected-but-missing binding gap (no-silent-under-declaration): a directly
    # casilla-bound binding whose enrolled resolver RAN (its source kind is in the
    # merged owned_sources, i.e. the source was present and resolved) but produced
    # NO value for that binding would otherwise fall through to a silent zero on
    # the initial-value path (binding not in binding_values, source not the
    # observation-backed previous_filing/relation_prefill carve-out). Mark those
    # ids unresolved so the formula leaf escapes non-blocking (mirroring the
    # relation channel) AND surface an INFORMATIONAL advisory. A binding whose
    # source is ABSENT (not in owned_sources) is a legitimate zero — the taxpayer
    # has no such data — and stays silent.
    _expected_missing = _expected_but_missing_binding_ids(
        snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources),
        resolved_binding_values=source_resolution.binding_values,
    )
    if _expected_missing:
        _missing_diagnostics = tuple(
            CalculationSourceDiagnostic(
                reason="unresolved_binding",
                source_kind=str(source),
                binding_id=binding_id,
                casilla_id=casilla_id,
                message=(
                    f"binding {binding_id!r} (casilla {casilla_id!r}) declares present source "
                    f"{source!r} whose resolver produced no value; the bound casilla would "
                    "otherwise default to a silent zero. Supply the source records before filing."
                ),
            )
            for binding_id, casilla_id, source in _expected_missing
        )
        source_resolution = source_resolution.model_copy(
            update={
                "unresolved_binding_ids": tuple(sorted({b for b, _c, _s in _expected_missing})),
                "diagnostics": source_resolution.diagnostics + _missing_diagnostics,
            },
        )
    return source_resolution


# Binding sources whose unresolved slot is ALREADY handled non-silently elsewhere
# and must NOT be re-flagged as an expected-but-missing silent zero:
#   - previous_filing / relation_prefill: the initial-value path treats an
#     unresolved slot of these as absent-by-design (operator-manual fallback) or
#     the relation channel already surfaces its own diagnostic;
#   - manual_input: the operator supplies the value directly.
_NON_SILENT_BOUND_BINDING_SOURCES: frozenset[str] = frozenset(
    {"previous_filing", "relation_prefill", "manual_input"},
)


def _expected_but_missing_binding_ids(
    revision: ModeloRevision,
    *,
    owned_sources: frozenset[BindingSourceKind],
    resolved_binding_values: Mapping[BindingId, Decimal],
) -> tuple[tuple[BindingId, CasillaId, BindingSourceKind], ...]:
    """Return (binding_id, casilla_id, source) for casilla-bound bindings whose present source resolved no value.

    A binding qualifies when (1) it is the binding of a ``BOUND`` casilla, (2) its
    source kind is in ``owned_sources`` (the resolver RAN for a present source),
    (3) it produced no value (absent from ``resolved_binding_values``), and (4) its
    source is not one of the non-silent carve-outs already handled by the
    initial-value path or the relation channel. The absent-source case (source not
    in ``owned_sources``) is a legitimate zero and is deliberately excluded.
    """
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    missing: list[tuple[BindingId, CasillaId, BindingSourceKind]] = []
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None:
            continue
        source = binding.source
        if str(source) in _NON_SILENT_BOUND_BINDING_SOURCES:
            continue
        if source not in owned_sources:
            continue
        if binding.id in resolved_binding_values:
            continue
        missing.append((binding.id, casilla.id, source))
    return tuple(missing)


def calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> BucketAggregationCalculationResult:
    """Calculate a modelo revision and return it alongside the source diagnostics.

    Identical orchestration to
    :func:`aeat.application.modelo.calculate_modelo_revision_from_bucket_aggregation`,
    but returns a
    :class:`BucketAggregationCalculationResult` carrying both the persisted
    :class:`CalculationRevision` and the NON-blocking
    :class:`aeat.application.aggregation.CalculationSourceDiagnostic` rows the
    source mesh raised while resolving the bucket ledger (the
    unconsumed-declarable-IVA advisories the operator-facing CLI surfaces so an
    unrouted observation is never silently under-declared).

    The bucket evidence is read from the injected
    :class:`TransactionCatalogueRepository` and
    :class:`InvoiceCatalogueRepository`; the source mesh projects their
    contributing rows plus previous-filing, relation-prefill, withholding,
    retenciones, and detail-row sources into the backend channels that feed the
    revision.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_unit, snapshot = _load_bucket_aggregation_context(
        work_unit_id,
        work_unit_repository=wu_repo,
    )

    # S26 boundary gate: reject any binding source that is neither enrolled in
    # the live resolver mesh nor explicitly deferred.  This converts a silent
    # blank into a loud error so a novel TOML source cannot slip through.
    assert_no_novel_source_kinds(snapshot.revision)

    # Refuse non-canonical casilla keys before source-collision and
    # bucket-merge checks compare them against registry casilla ids.
    if casilla_inputs is not None:
        casilla_inputs = _validate_casilla_input_ids(snapshot.revision, casilla_inputs)

    # Use the LOCK set (deterministic ledger resolvers only) for the pre-merge
    # caller-override guard.  Optional-return resolvers (previous_filing, profile,
    # OSS, invoices) are absent from the lock so carry-forward overrides and
    # test fixtures remain valid. See BUCKET_AGGREGATION_LOCK_SOURCES.
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    source_resolution = _resolve_bucket_source_mesh(
        snapshot,
        work_unit,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
    )
    # Precedence ladder step 4 (ADR ruling D2, extended): re-run the guard against
    # the merged owned-sources, but EXCLUDE the caller-overridable CARRY sources
    # (previous_filing, relation_prefill, iva_compensation_annual_partition). A
    # caller --binding override of an automatically-carried prior value is
    # legitimate and must reach the engine, where the casilla-lift no-ops on the
    # already-resolved binding and the engine's consistency check adjudicates any
    # divergence. Every other dynamically-discovered mesh source (the ledger
    # aggregations) stays guarded so the persisted revision reflects the sources
    # it claims to aggregate.
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources) - CALLER_OVERRIDABLE_CARRY_SOURCES,
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    all_detail_rows = (*source_resolution.detail_rows, *detail_rows)
    _raise_if_m349_intracom_ledger_rows_need_operator_rows(
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        detail_rows=all_detail_rows,
    )
    detail_row_binding_values = _detail_row_binding_values_for_calculation(
        work_unit=work_unit,
        detail_rows=detail_rows,
    )
    backend_binding_values = _merge_detail_row_binding_values(
        source_resolution.binding_values,
        detail_row_binding_values,
    )
    backend_source_inputs = {
        **dict(source_resolution.bound_inputs_by_casilla_id),
        **resolve_available_bound_inputs_by_casilla_id(
            snapshot.revision,
            backend_binding_values,
        ),
    }
    backend_inputs = _merge_bucket_bound_inputs(
        revision=snapshot.revision,
        casilla_inputs=casilla_inputs or {},
        bound_inputs=backend_source_inputs,
    )
    # Feed the relation-resolver's resolved relation_values onto the engine's
    # first-class relation channel so computed casillas that reference
    # ``{ relation = ... }`` operands fire. A caller --relation override still
    # wins (precedence ladder step 4, D2 carve-out for relation carries): an
    # operator override of an auto-carried relation value is legitimate.
    merged_relation_values = {**source_resolution.relation_values, **dict(relation_values or {})}
    caller_relation_ids = frozenset((relation_values or {}).keys())
    unresolved_relation_ids = tuple(
        relation_id
        for relation_id in source_resolution.unresolved_relation_ids
        if relation_id not in caller_relation_ids
    )
    # A caller --binding override of an expected-but-missing binding RESOLVES it,
    # so drop it from the unresolved set and its advisory (mirrors the relation
    # caller-override carve-out above).
    caller_binding_ids = frozenset((binding_values or {}).keys())
    unresolved_binding_ids = tuple(
        binding_id
        for binding_id in source_resolution.unresolved_binding_ids
        if binding_id not in caller_binding_ids and binding_id not in detail_row_binding_values
    )
    source_diagnostics = tuple(
        diagnostic
        for diagnostic in source_resolution.diagnostics
        if (diagnostic.relation_id is None or diagnostic.relation_id not in caller_relation_ids)
        and (
            diagnostic.binding_id is None
            or (
                diagnostic.binding_id not in caller_binding_ids
                and diagnostic.binding_id not in detail_row_binding_values
            )
        )
    )
    revision = calculate_modelo_revision(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs or {},
        binding_values=binding_values or {},
        backend_binding_values=backend_binding_values,
        backend_casilla_inputs=backend_inputs,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        ledger_preflight_transaction_repository=transaction_repository,
        enum_binding_values=enum_binding_values,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=merged_relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        source_transaction_ids=tuple(source_resolution.source_transaction_ids),
        filing_period_date=filing_period_date,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=all_detail_rows,
        clock=clock,
    )
    advisory_diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        snapshot.revision,
        revision.casilla_values,
        modelo=work_unit.modelo,
        period_token=work_unit.period.registry_token,
        filing_year=work_unit.filing_year,
    )
    source_diagnostics = source_diagnostics + advisory_diagnostics
    return BucketAggregationCalculationResult(
        revision=revision,
        source_diagnostics=source_diagnostics,
    )


def _detail_row_binding_values_for_calculation(
    *,
    work_unit: WorkUnit,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> dict[BindingId, Decimal]:
    if str(work_unit.modelo) != Modelo.M349.value:
        return {}
    operador_rows = tuple(row for row in detail_rows if isinstance(row, Modelo349OperadorRow))
    if not operador_rows:
        return {}
    importe_operaciones = sum((row.importe for row in operador_rows), Decimal("0"))
    return {
        _M349_NUMERO_OPERADORES_BINDING: Decimal(len(operador_rows)),
        _M349_IMPORTE_OPERACIONES_BINDING: importe_operaciones,
        _M349_NUMERO_RECTIFICACIONES_BINDING: Decimal("0"),
        _M349_IMPORTE_RECTIFICACIONES_BINDING: Decimal("0"),
    }


def _merge_detail_row_binding_values(
    source_binding_values: Mapping[BindingId, Decimal],
    detail_row_binding_values: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    merged = dict(source_binding_values)
    for binding_id, value in detail_row_binding_values.items():
        merged[binding_id] = merged.get(binding_id, Decimal("0")) + value
    return merged


def _merge_bucket_bound_inputs(
    *,
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaId, Decimal],
    bound_inputs: Mapping[CasillaId, Decimal],
) -> dict[CasillaId, Decimal]:
    casillas = casillas_by_id(revision)
    computed = sorted(
        casilla_id
        for casilla_id in bound_inputs
        if casilla_id in casillas and casillas[casilla_id].input_kind == InputKind.COMPUTED
    )
    if computed:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.computed_casilla_binding_conflict",
            context={"computed": computed},
        )
    return dict(sorted({**bound_inputs, **casilla_inputs}.items()))


def _previous_filing_resolution_excluding_iva_compensation(
    resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Strip the M303 IVA-compensation binding from a previous_filing resolution.

    ADR ruling D3: the iva-wallet compensación decision owns the
    ``modelo-303-compensacion-pendiente-anteriores`` binding. The cross-period
    carry resolver must NOT also emit it, or the two write paths would
    double-count the prior carry-forward balance. This drops both the binding
    value and any matching provenance row before the resolution enters the
    source mesh.

    Because :class:`aeat.application.aggregation.CalculationSourceResolution`
    is immutable, the exclusion returns a copied resolution with only the 303
    compensation binding and its provenance removed.
    """
    from ..calculations._binding_prefill import _MODELO_303_IVA_COMPENSATION_BINDING_ID

    excluded = _MODELO_303_IVA_COMPENSATION_BINDING_ID
    if excluded not in resolution.binding_values:
        return resolution
    return resolution.model_copy(
        update={
            "binding_values": {k: v for k, v in resolution.binding_values.items() if k != excluded},
            "provenance": tuple(item for item in resolution.provenance if not item.source_ref.endswith(f":{excluded}")),
        },
    )


def _iva_compensation_previous_filing_exclusions() -> frozenset[BindingId]:
    """Binding ids previous-filing must not resolve because the IVA wallet owns them."""
    from ..calculations._binding_prefill import _MODELO_303_IVA_COMPENSATION_BINDING_ID

    return frozenset({_MODELO_303_IVA_COMPENSATION_BINDING_ID})


def _source_resolution_excluding_iva_compensation(
    revision: ModeloRevision,
    resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Keep Modelo 303 prior-compensation owned exclusively by the IVA wallet."""
    from ..calculations._binding_prefill import _MODELO_303_IVA_COMPENSATION_BINDING_ID

    excluded = _MODELO_303_IVA_COMPENSATION_BINDING_ID
    relation_ids = frozenset(rel.id for rel in revision.relations if rel.target_binding == excluded)
    if excluded not in resolution.binding_values and not relation_ids.intersection(resolution.relation_values):
        return resolution
    return resolution.model_copy(
        update={
            "binding_values": {k: v for k, v in resolution.binding_values.items() if k != excluded},
            "relation_values": {k: v for k, v in resolution.relation_values.items() if k not in relation_ids},
            "provenance": tuple(
                item
                for item in resolution.provenance
                if not item.source_ref.endswith(f":{excluded}") and item.source_ref.split(":", 1)[0] not in relation_ids
            ),
        },
    )


def assert_no_novel_source_kinds(revision: ModeloRevision) -> None:
    """Raise if any binding source kind is unknown to the live mesh (S26 boundary gate).

    A binding whose ``source`` is not in the enrolled-resolver union, the
    explicitly-deferred set, or ``manual_input`` would silently blank on every
    calculation.  This gate converts that silent blank into a loud
    :exc:`ModeloAggregationBindingError` at calculation time so a novel TOML
    source cannot compile into a silently-zero revision.

    The accepted set is:

    * ``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS`` — enrolled resolvers plus
      explicitly deferred advisory sources.

    Args:
        revision: The :class:`ModeloRevision` whose binding source kinds are
            checked against the live source-mesh enrollment.

    Raises:
        ModeloAggregationBindingError: When a binding carries a source kind
            absent from both the enrolled and the deferred sets.
    """
    novel = sorted(
        {
            str(binding.source)
            for binding in revision.bindings
            if str(binding.source) not in ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS
        },
    )
    if novel:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.novel_source_kind_rejected",
            context={"novel_source_kinds": novel, "revision_id": revision.id},
        )


def _source_owned_binding_ids(
    revision: ModeloRevision, owned_sources: frozenset[BindingSourceKind]
) -> frozenset[BindingId]:
    return frozenset(binding.id for binding in revision.bindings if binding.source in owned_sources)


def _source_owned_bound_casilla_ids(
    revision: ModeloRevision, owned_sources: frozenset[BindingSourceKind]
) -> frozenset[CasillaId]:
    source_owned_binding_ids = _source_owned_binding_ids(revision, owned_sources)
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND
        and source_owned_binding_ids.intersection(bound_casilla_binding_ids(casilla))
    )


def _reject_caller_overrides_of_source_bindings(
    *,
    revision: ModeloRevision,
    owned_sources: frozenset[BindingSourceKind],
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_casilla_inputs: Mapping[CasillaId, Decimal],
) -> None:
    """Refuse caller-supplied bindings or casilla inputs that collide with values bucket source resolvers own.

    Bucket-aggregation calculation derives source-owned binding values
    (and the casillas bound to them) from bucket substrate. Letting a
    caller override those silently would break calculation grounding:
    the persisted revision would no longer reflect the sources it claims
    to aggregate. Both collisions are rejected before any value reaches
    the engine.
    """
    rejected_bindings = sorted(
        set(caller_binding_values).intersection(_source_owned_binding_ids(revision, owned_sources)),
    )
    if rejected_bindings:
        # For the IVA compensation binding the operator should use the seed verb, not
        # a manual override, to set the prior carry-forward balance.
        seed_suggestion = (
            "aeat app modelo iva-wallet seed"
            if any("compensacion-pendiente-anteriores" in b for b in rejected_bindings)
            else None
        )
        raise ModeloAggregationBindingError(
            translated_message="errors.error.error_modelo_aggregation_binding",
            suggestion=seed_suggestion,
        )
    rejected_casillas = sorted(
        set(caller_casilla_inputs).intersection(_source_owned_bound_casilla_ids(revision, owned_sources)),
    )
    if rejected_casillas:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.caller_casilla_source_binding_conflict",
            context={"casillas": rejected_casillas},
        )


def list_calculation_revisions(
    *,
    work_unit_id: str | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> tuple[CalculationRevision, ...]:
    """List calculation revisions, optionally filtered to one work unit.

    Results are sorted by ``(work_unit_id, created_at)`` so the
    chronological revision chain for one work unit is contiguous
    and stable across calls.

    Each element is a :class:`CalculationRevision`.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revisions = tuple(
        revision for revision in catalogue.values() if work_unit_id is None or revision.work_unit_id == work_unit_id
    )
    return tuple(sorted(revisions, key=lambda r: (r.work_unit_id, r.created_at)))


def get_calculation_revision(
    calculation_revision_id: str,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> CalculationRevision:
    """Return one calculation revision by id, or raise.

    Returns the :class:`CalculationRevision` matching
    ``calculation_revision_id``.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    return revision


def mark_revision_verificado_completo(
    calculation_revision_id: str,
    *,
    actor: str,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Transition a draft revision to ``VERIFICADO_COMPLETO``.

    The revision must currently be in ``BORRADOR`` state. After the
    transition the revision is immutable; subsequent calculation
    work on the same work unit must produce a new revision.

    Args:
        calculation_revision_id: The id of the draft revision to promote.
        actor: Operator identifier stamped as ``verified_by``.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        work_unit_repository: Optional work-unit catalogue repository
            override used to refuse direct promotion for cross-period
            dependency revisions.
        clock: Optional UTC timestamp override for ``verified_at``.

    Returns:
        The updated :class:`CalculationRevision` in ``VERIFICADO_COMPLETO`` state.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not
            currently in ``BORRADOR`` state.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    existing = catalogue.get(calculation_revision_id)
    if existing is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if existing.state is not CalculationRevisionState.BORRADOR:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{existing.state.value!r}; only DRAFT revisions can be marked verified-complete",
        )
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_unit = wu_repo.load().get(existing.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": existing.work_unit_id},
        )
    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(work_unit)
    _refuse_direct_cross_period_verification(existing, work_unit_repository=wu_repo)
    now = clock or _utc_now()
    verified = existing.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        },
    )
    cr_repo.save(upsert_calculation_revision(catalogue, verified))
    return verified


def _refuse_direct_cross_period_verification(
    revision: CalculationRevision,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
) -> None:
    """Require the full verification pipeline for cross-period dependency revisions."""
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_unit = wu_repo.load().get(revision.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": revision.work_unit_id},
        )
    snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    if tuple(_cross_period_dependency_requirements(snapshot)):
        raise ModeloCrossPeriodCleanStateError(
            translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
            context={
                "calculation_revision_id": revision.calculation_revision_id,
                "work_unit_id": revision.work_unit_id,
                "modelo": work_unit.modelo,
                "filing_year": str(work_unit.filing_year),
                "period": work_unit.period.registry_token,
            },
            suggestion="aeat app modelo work verify",
        )
