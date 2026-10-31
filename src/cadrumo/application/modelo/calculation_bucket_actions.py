"""Bucket source orchestration and calculation diagnostics.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`,
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection
from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.identifiers import canonical_decimal_string as _canonical_decimal_string
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
)
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.calculation_revision_sources import (
    CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT,
    CalculationSourceIssue,
    CalculationSourceRef,
)
from ...domain.modelos.row_models import Modelo210AgrupacionRentaRow, ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..user_profile.projections import profile_fact_index
from ._calculation_aggregation_context import load_bucket_aggregation_context as _load_bucket_aggregation_context
from ._calculation_modelo_adjustments import (
    calculated_decimal as _calculated_decimal,
)
from ._calculation_modelo_adjustments import (
    detail_row_binding_values_for_calculation as _detail_row_binding_values_for_calculation,
)
from ._calculation_modelo_adjustments import (
    union_detail_rows_by_identity as _union_detail_rows_by_identity,
)
from ._m349_ledger_guard import (
    raise_if_m349_intracom_ledger_rows_need_operator_rows as _raise_if_m349_intracom_ledger_rows_need_operator_rows,
)
from ._operator_override_advisory import collect_operator_override_divergence_diagnostics
from ._registry_helpers import validate_casilla_input_ids as _validate_casilla_input_ids
from ._transaction_catalogue_cache import MemoizedTransactionCatalogueRepository
from .action_errors import (
    ModeloAggregationBindingError,
)
from .calculation_action_ports import (
    CalculationActionPorts,
)
from .calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .calculation_notes import CALCULATION_NOTES, PRINTED_BOX_REASONS, durable_binding_source
from .calculation_publication import CalculationRevisionPublication
from .calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES, CALLER_OVERRIDABLE_CARRY_SOURCES
from .printed_boxes import PrintedBoxes, snapshot_printed_boxes
from .profile_export_binding import profile_text_casilla_gap_diagnostics
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...core.secure_object_write import SecureObjectWrite
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.detail_record_bindings import Modelo720RowObservation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ..aggregation.foreign_assets import ForeignAssetIngestObservation
    from ..aggregation.source_mesh import (
        CalculationSourceResolution,
    )


from .calculation_actions import calculate_modelo_revision_with_trusted_mesh_sources
from .calculation_source_guards import (
    assert_no_novel_source_kinds,
    m210_gross_source_mode,
    reject_caller_overrides_of_source_bindings,
)
from .calculation_source_mesh_actions import resolve_bucket_source_mesh


@dataclass(frozen=True, slots=True)
class BucketAggregationCalculationResult:
    """Calculation revision plus the non-blocking source diagnostics raised while resolving it.

    ``revision`` is the persisted :class:`CalculationRevision`; ``profile`` is
    the work profile the calculation checked and read.
    ``source_diagnostics`` carries the
    :class:`~application.aggregation.source_mesh.CalculationSourceDiagnostic` rows the
    source mesh emitted during resolution, notably the unconsumed-declarable-IVA
    advisories (a declarable IVA observation no ``ledger_iva_aggregation``
    binding selects). They are NON-blocking: the revision was computed and
    persisted regardless. Surfacing them keeps an unrouted declarable
    observation from being silently under-declared (no-silent-under-declaration).
    """

    revision: CalculationRevision
    profile: ModeloWorkProfile
    publication: CalculationRevisionPublication
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class _BucketAggregationPreparation:
    """Validated caller inputs plus the bucket context selected for one run."""

    work_unit: WorkUnit
    snapshot: RegistrySnapshot
    profile: ModeloWorkProfile
    casilla_inputs: Mapping[CasillaId, Decimal]
    source_casilla_inputs: Mapping[CasillaId, Decimal] | None
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None
    binding_values: Mapping[BindingId, Decimal]
    source_binding_values: Mapping[BindingId, Decimal] | None
    relation_values: Mapping[RelationId, Decimal]
    source_relation_values: Mapping[RelationId, Decimal] | None


@dataclass(frozen=True, slots=True)
class _BucketAggregationChannels:
    """Mesh-derived channels and diagnostics ready for calculation persistence."""

    source_resolution: CalculationSourceResolution
    detail_rows: tuple[ModeloDetailRow, ...]
    backend_binding_values: Mapping[BindingId, Decimal]
    backend_casilla_inputs: Mapping[CasillaId, Decimal]
    override_diagnostics: tuple[CalculationSourceDiagnostic, ...]
    reconciliation: _CallerOverrideReconciliation


def _source_provenance_refs(
    source_resolution: CalculationSourceResolution,
) -> tuple[CalculationSourceRef, ...]:
    """Project the mesh resolution's application provenance into persisted domain refs.

    Maps each :class:`~application.aggregation.source_mesh.CalculationSourceProvenance`
    row (the resolver→source-object→fingerprint trace) into the domain-side
    :class:`~CalculationSourceRef` that
    :func:`~application.modelo.revision_persistence.persist_calculation_revision`
    persists on the :class:`~CalculationRevision`. This is the
    application→domain boundary map: the domain never imports the application
    provenance model, and the compact ref deliberately drops the per-casilla
    ``legal_refs`` / ``source_refs`` (carried by the revision's ``observations``)
    to avoid duplicating that grounding. ``dependency_treatment`` is NOT dropped:
    unlike the per-casilla refs, nothing else on the revision carries it, so it
    survives onto the persisted ref unchanged. ``source_casilla_ids`` is also NOT
    dropped: it is a subject identity, not grounding, and the anti-
    duplication rationale for ``legal_refs``/``source_refs`` does not extend to
    it -- nothing else on the revision recovers which casilla a general
    (non-row-materialized) source object explains. ``source_filing_year`` is
    kept for the same reason: it is the only persisted trace of a Modelo 193
    disclosure phase row's accrual year, which tells a settled prior-accrual
    row from a pending one.
    """
    return tuple(
        CalculationSourceRef(
            resolver_id=provenance.resolver_id,
            resolved_binding_source=provenance.resolved_binding_source,
            contributor_source_kind=provenance.contributor_source_kind,
            contributor_binding_source=provenance.contributor_binding_source,
            lineage_role=provenance.lineage_role,
            source_ref=provenance.source_ref,
            parent_source_ref=provenance.parent_source_ref,
            fingerprint=provenance.fingerprint,
            source_casilla_ids=provenance.source_casilla_ids,
            dependency_treatment=provenance.dependency_treatment,
            source_filing_year=provenance.source_filing_year,
        )
        for provenance in source_resolution.provenance
    )


@dataclass(frozen=True, slots=True)
class _CallerOverrideReconciliation:
    """Reconciliation of caller overrides against the merged source resolution.

    Carries the values the trusted-mesh calculate call and the diagnostics
    surface consume after caller ``--binding`` / ``--relation`` overrides have
    been folded into the mesh-resolved relation channel and the unresolved /
    advisory sets have been narrowed to exclude the caller-resolved ids. The
    diagnostics filtering is set-identical to the pre-extraction inline algebra
    (no-silent-under-declaration).
    """

    merged_relation_values: dict[RelationId, Decimal]
    unresolved_relation_ids: tuple[RelationId, ...]
    unresolved_binding_ids: tuple[BindingId, ...]
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...]


def _caller_relation_values_from_bindings(
    revision: ModeloRevision,
    target_period: str,
    caller_binding_values: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    """Project caller --binding overrides of fold slots into the fold-value channel.

    A caller --binding override of a relation-prefill slot also resolves that
    fold for formula operands, scoped to the periods the binding's own
    applicability admits.
    """
    return {
        binding.id: _calculated_decimal(caller_binding_values[binding.id])
        for binding, _ in relation_prefill_bindings_for_period(revision, period=target_period)
        if binding.id in caller_binding_values
    }


def _orphaned_override_diagnostics(
    revision: ModeloRevision,
    *,
    caller_relation_values: Mapping[RelationId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on every relation override whose key no binding of this revision carries.

    The fold slot IS the binding now, so the relation channel is keyed by
    binding id. An override under any other key -- a retired pre-absorption
    relation id above all, but equally a typo or a key inherited from a
    different modelo -- is merged into the channel, matches nothing the engine
    reads, and vanishes. Vanishes is the operative word: the operator entered a
    figure, the result does not contain it, and nothing anywhere says so. That
    is a silent under-declaration whenever the figure would have reduced the
    amount owed, and it is undetectable from the output.

    Advisory rather than blocking. The interactive ``--relation`` surface
    already refuses an unknown key outright at the input boundary, so what
    reaches here is a PERSISTED override replayed against a revision that no
    longer declares its key -- a stored fact, not a fresh mistake, and refusing
    it would make an old catalogue entry uncalculable rather than merely
    explicable.
    """
    declared_binding_ids = {binding.id for binding in revision.bindings}
    return tuple(
        CalculationSourceDiagnostic(
            reason="orphaned_override",
            source_kind="relation_prefill",
            binding_source=BindingSourceKind.RELATION_PREFILL,
            relation_id=override_key,
            message=(
                f"override {override_key!r} names no binding this revision declares, so its value "
                "reaches no casilla and does not appear in the result"
            ),
            remedy=(
                "re-enter the figure against a binding this revision declares, or drop it if the "
                "slot it belonged to no longer exists"
            ),
        )
        for override_key in sorted(caller_relation_values)
        if override_key not in declared_binding_ids
    )


def _caller_resolved_source_diagnostics(
    source_resolution: CalculationSourceResolution,
    *,
    caller_resolved_relation_ids: frozenset[RelationId],
    caller_binding_ids: frozenset[BindingId],
    detail_row_binding_values: Mapping[BindingId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Drop advisories whose relation or binding a caller override resolved (set-identical)."""
    return tuple(
        diagnostic
        for diagnostic in source_resolution.diagnostics
        if (diagnostic.relation_id is None or diagnostic.relation_id not in caller_resolved_relation_ids)
        and (
            diagnostic.binding_id is None
            or (
                diagnostic.binding_id not in caller_binding_ids
                and diagnostic.binding_id not in detail_row_binding_values
            )
        )
    )


def _reconcile_caller_overrides(
    *,
    revision: ModeloRevision,
    target_period: str,
    source_resolution: CalculationSourceResolution,
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_relation_values: Mapping[RelationId, Decimal],
    detail_row_binding_values: Mapping[BindingId, Decimal],
) -> _CallerOverrideReconciliation:
    """Fold caller overrides into the relation channel and narrow the unresolved / advisory sets.

    A caller ``--binding`` override of a relation's target binding resolves that
    relation for formula operands, and a caller ``--binding`` / ``--relation``
    override of an automatically-carried prior value resolves the corresponding
    unresolved binding / relation and drops its advisory. This helper carries the
    caller-override carve-out algebra that used to live inline in
    :func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`;
    the diagnostics filtering stays set-identical.
    """
    caller_relation_values_from_bindings = _caller_relation_values_from_bindings(
        revision,
        target_period,
        caller_binding_values,
    )
    # Feed the relation-resolver's resolved relation_values onto the engine's
    # first-class relation channel so computed casillas that reference
    # ``{ relation = ... }`` operands fire. A caller --binding override of a
    # relation's target binding also resolves that relation for formula operands;
    # this keeps the public binding override contract aligned with relation-only
    # formulas such as M100 0604. A caller --relation override remains the most
    # explicit value and wins last.
    merged_relation_values = {
        **source_resolution.relation_values,
        **caller_relation_values_from_bindings,
        **dict(caller_relation_values or {}),
    }
    caller_relation_ids = frozenset((caller_relation_values or {}).keys())
    caller_resolved_relation_ids = caller_relation_ids | frozenset(caller_relation_values_from_bindings)
    unresolved_relation_ids = tuple(
        relation_id
        for relation_id in source_resolution.unresolved_relation_ids
        if relation_id not in caller_resolved_relation_ids
    )
    # A caller --binding override of an expected-but-missing binding RESOLVES it,
    # so drop it from the unresolved set and its advisory (mirrors the relation
    # caller-override carve-out above).
    caller_binding_ids = frozenset(caller_binding_values)
    unresolved_binding_ids = tuple(
        binding_id
        for binding_id in source_resolution.unresolved_binding_ids
        if binding_id not in caller_binding_ids and binding_id not in detail_row_binding_values
    )
    source_diagnostics = _caller_resolved_source_diagnostics(
        source_resolution,
        caller_resolved_relation_ids=caller_resolved_relation_ids,
        caller_binding_ids=caller_binding_ids,
        detail_row_binding_values=detail_row_binding_values,
    ) + _orphaned_override_diagnostics(
        revision,
        caller_relation_values=caller_relation_values or {},
    )
    return _CallerOverrideReconciliation(
        merged_relation_values=merged_relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        source_diagnostics=source_diagnostics,
    )


def _resolved_m210_gross_income_mode(
    work_unit: WorkUnit,
    *,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
    m210_official_tipo_renta_code: str | None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> M210GrossIncomeSourceMode | None:
    """Resolve the M210 gross-income source mode and refuse the overrides it forbids.

    Ledger mode owns the gross-income figure, so a manual casilla override, an
    absent or contradictory official tipo-renta selection, and operator-supplied
    agrupacion rows are each refused here rather than silently losing to the
    ledger projection downstream.
    """
    mode = m210_gross_source_mode(work_unit, m210_gross_income_source_mode)
    _reject_manual_m210_gross_income_override_in_ledger_mode(
        mode=mode,
        casilla_inputs=casilla_inputs or {},
    )
    _validate_m210_official_tipo_renta_selection(
        mode=mode,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        text_casilla_inputs=text_casilla_inputs or {},
    )
    _reject_manual_m210_agrupacion_rows_in_ledger_mode(
        mode=mode,
        detail_rows=detail_rows,
    )
    return mode


def _prepare_bucket_aggregation_calculation(
    *,
    work_unit_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    m210_official_tipo_renta_code: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
    binding_values: Mapping[BindingId, Decimal] | None,
    relation_values: Mapping[RelationId, Decimal] | None,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    detail_rows: tuple[ModeloDetailRow, ...],
    profile: ModeloWorkProfile | None,
) -> _BucketAggregationPreparation:
    """Load, validate, and protect caller channels before source resolution."""
    work_unit, snapshot, checked_profile = _load_bucket_aggregation_context(
        work_unit_id,
        work_unit_repository=work_unit_repository,
        profile=profile,
        operation=operation,
    )
    assert_no_novel_source_kinds(snapshot.revision)
    validated_casilla_inputs = _validated_bucket_casilla_inputs(snapshot, casilla_inputs)
    resolved_m210_gross_income_source_mode = _resolved_m210_gross_income_mode(
        work_unit,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        casilla_inputs=validated_casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        detail_rows=detail_rows,
    )
    caller_binding_values = binding_values or {}
    reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
        caller_binding_values=caller_binding_values,
        caller_casilla_inputs=validated_casilla_inputs,
    )
    return _BucketAggregationPreparation(
        work_unit=work_unit,
        snapshot=snapshot,
        profile=checked_profile,
        casilla_inputs=validated_casilla_inputs,
        source_casilla_inputs=casilla_inputs if casilla_inputs is None else validated_casilla_inputs,
        m210_gross_income_source_mode=resolved_m210_gross_income_source_mode,
        binding_values=caller_binding_values,
        source_binding_values=binding_values,
        relation_values=relation_values or {},
        source_relation_values=relation_values,
    )


def _validated_bucket_casilla_inputs(
    snapshot: RegistrySnapshot,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
) -> Mapping[CasillaId, Decimal]:
    """Return canonical caller casillas before source ownership checks."""
    if casilla_inputs is None:
        return dict[CasillaId, Decimal]()
    validated_inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in _validate_casilla_input_ids(snapshot.revision, casilla_inputs).items():
        validated_inputs[casilla_id] = _require_decimal_input(value)
    return validated_inputs


def _require_decimal_input(value: object) -> Decimal:
    """Keep the source-mesh contract concrete at the engine boundary."""
    if not isinstance(value, Decimal):
        raise TypeError(f"validated casilla input is not a Decimal: {value!r}")
    return value


def _resolve_bucket_aggregation_source_resolution(
    *,
    preparation: _BucketAggregationPreparation,
    ports: CalculationActionPorts,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...],
    foreign_asset_row_observations: tuple[Modelo720RowObservation, ...],
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    m210_official_tipo_renta_code: str | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    filing_period_date: date | None,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> CalculationSourceResolution:
    """Resolve the mesh, then enforce its final exclusive ownership set."""
    source_resolution = resolve_bucket_source_mesh(
        preparation.snapshot,
        preparation.work_unit,
        ports=ports,
        foreign_asset_observations=foreign_asset_observations,
        foreign_asset_row_observations=foreign_asset_row_observations,
        casilla_inputs=preparation.source_casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=preparation.m210_gross_income_source_mode,
        binding_values=preparation.source_binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=preparation.source_relation_values,
        filing_period_date=filing_period_date,
        profile=preparation.profile,
        transaction_repository=transaction_repository,
    )
    reject_caller_overrides_of_source_bindings(
        revision=preparation.snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources) - CALLER_OVERRIDABLE_CARRY_SOURCES,
        caller_binding_values=preparation.binding_values,
        caller_casilla_inputs=preparation.casilla_inputs,
        caller_enum_binding_values=enum_binding_values,
        closed_record_row_sets=source_resolution.closed_record_row_sets,
    )
    return source_resolution


def _bucket_aggregation_channels(
    *,
    preparation: _BucketAggregationPreparation,
    source_resolution: CalculationSourceResolution,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> _BucketAggregationChannels:
    """Compose mesh, detail-row, and caller channels in their established order."""
    all_detail_rows = _union_detail_rows_by_identity(
        resolver_rows=source_resolution.detail_rows,
        caller_rows=detail_rows,
    )
    _raise_if_m349_intracom_ledger_rows_need_operator_rows(
        work_unit=preparation.work_unit,
        transaction_repository=transaction_repository,
        detail_rows=all_detail_rows,
    )
    detail_row_binding_values = _detail_row_binding_values_for_calculation(
        work_unit=preparation.work_unit,
        revision=preparation.snapshot.revision,
        detail_rows=detail_rows,
    )
    backend_binding_values = _merge_detail_row_binding_values(
        source_resolution.binding_values,
        detail_row_binding_values,
    )
    backend_source_inputs = _source_bound_casilla_inputs(
        preparation.snapshot.revision,
        source_resolution=source_resolution,
        backend_binding_values=backend_binding_values,
    )
    backend_casilla_inputs = _merge_bucket_bound_inputs(
        revision=preparation.snapshot.revision,
        casilla_inputs=preparation.casilla_inputs,
        bound_inputs=backend_source_inputs,
    )
    override_diagnostics = collect_operator_override_divergence_diagnostics(
        preparation.snapshot.revision,
        casilla_inputs=preparation.casilla_inputs,
        bound_inputs=backend_source_inputs,
    )
    reconciliation = _reconcile_caller_overrides(
        revision=preparation.snapshot.revision,
        target_period=preparation.work_unit.period.registry_token,
        source_resolution=source_resolution,
        caller_binding_values=preparation.binding_values,
        caller_relation_values=preparation.relation_values,
        detail_row_binding_values=detail_row_binding_values,
    )
    return _BucketAggregationChannels(
        source_resolution=source_resolution,
        detail_rows=all_detail_rows,
        backend_binding_values=backend_binding_values,
        backend_casilla_inputs=backend_casilla_inputs,
        override_diagnostics=override_diagnostics,
        reconciliation=reconciliation,
    )


def _source_bound_casilla_inputs(
    revision: ModeloRevision,
    *,
    source_resolution: CalculationSourceResolution,
    backend_binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Merge direct source casillas with the registry's bound-casilla lift."""
    return {
        **dict(source_resolution.bound_inputs_by_casilla_id),
        **resolve_available_bound_inputs_by_casilla_id(revision, backend_binding_values),
    }


def _caller_operator_layer(
    *,
    preparation: _BucketAggregationPreparation,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    enum_binding_values: Mapping[BindingId, str] | None,
) -> CalculationOperatorLayer:
    """Project the validated caller tier of one run onto the persisted operator layer.

    Only the caller channels are read: the backend, bound, profile and borrador
    tiers merged into the revision's replay maps never reach the layer, so a
    later replay cannot promote a source value into an operator override.
    """
    return CalculationOperatorLayer(
        decimal_casilla_inputs={
            casilla_id: _canonical_decimal_string(value) for casilla_id, value in preparation.casilla_inputs.items()
        },
        text_casilla_inputs=dict(text_casilla_inputs or {}),
        binding_overrides={
            **{
                binding_id: _canonical_decimal_string(value) for binding_id, value in preparation.binding_values.items()
            },
            **dict(enum_binding_values or {}),
        },
    )


def calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    record_operator_layer: bool = False,
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    iva_compensation_decision: object | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...] = (),
    foreign_asset_row_observations: tuple[Modelo720RowObservation, ...] = (),
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    clock: datetime | None = None,
    additional_secure_object_writes_for_revision: (
        Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None
    ) = None,
    profile: ModeloWorkProfile | None = None,
) -> BucketAggregationCalculationResult:
    """Calculate from bucket sources and return the revision with diagnostics."""
    ports.relation_override_migration.migrate(ports.calculation_repository, operation=ports.operation)
    preparation = _prepare_bucket_aggregation_calculation(
        work_unit_id=work_unit_id,
        work_unit_repository=ports.work_unit_repository,
        operation=ports.operation,
        casilla_inputs=casilla_inputs,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        binding_values=binding_values,
        relation_values=relation_values,
        text_casilla_inputs=text_casilla_inputs,
        detail_rows=detail_rows,
        profile=profile,
    )
    # The source mesh and the ledger snapshot anchor both consume the same
    # immutable contributor rows during one calculation. Keep the existing
    # calculation-scoped read-through cache alive through the anchor so the
    # latter does not decrypt/validate the exact contributor ids a second time.
    memoized_transaction_repository = MemoizedTransactionCatalogueRepository(ports.transaction_repository)
    source_resolution = _resolve_bucket_aggregation_source_resolution(
        preparation=preparation,
        ports=ports,
        foreign_asset_observations=foreign_asset_observations,
        foreign_asset_row_observations=foreign_asset_row_observations,
        text_casilla_inputs=text_casilla_inputs,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        enum_binding_values=enum_binding_values,
        filing_period_date=filing_period_date,
        transaction_repository=memoized_transaction_repository,
    )
    channels = _bucket_aggregation_channels(
        preparation=preparation,
        source_resolution=source_resolution,
        transaction_repository=memoized_transaction_repository,
        detail_rows=detail_rows,
    )
    publication = calculate_modelo_revision_with_trusted_mesh_sources(
        work_unit_id,
        ports=ports,
        actor=actor,
        casilla_inputs=preparation.casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=(
            _caller_operator_layer(
                preparation=preparation,
                text_casilla_inputs=text_casilla_inputs,
                enum_binding_values=enum_binding_values,
            )
            if record_operator_layer
            else None
        ),
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=preparation.m210_gross_income_source_mode,
        binding_values=preparation.binding_values,
        backend_binding_values=channels.backend_binding_values,
        row_binding_values=channels.source_resolution.row_binding_values,
        row_source_identities=channels.source_resolution.row_source_identities,
        closed_record_row_sets=channels.source_resolution.closed_record_row_sets,
        row_casilla_values=channels.source_resolution.row_casilla_values,
        row_casilla_provenance=channels.source_resolution.row_casilla_provenance,
        backend_casilla_inputs=channels.backend_casilla_inputs,
        iva_compensation_decision=iva_compensation_decision,
        enum_binding_values={
            **dict(channels.source_resolution.enum_binding_values),
            **dict(enum_binding_values or {}),
        },
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=channels.reconciliation.merged_relation_values,
        unresolved_relation_ids=channels.reconciliation.unresolved_relation_ids,
        unresolved_binding_ids=channels.reconciliation.unresolved_binding_ids,
        source_transaction_ids=tuple(channels.source_resolution.source_transaction_ids),
        source_provenance=_source_provenance_refs(channels.source_resolution),
        source_issues=_unrouted_source_issues(
            channels.reconciliation.source_diagnostics,
            snapshot_printed_boxes(ports.operation, preparation.snapshot),
        ),
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=(
            channels.source_resolution.m303_regimen_simplificado_annual_summary_handoff
        ),
        filing_period_date=filing_period_date,
        detail_rows=channels.detail_rows,
        clock=clock,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
        profile=preparation.profile,
        transaction_repository=memoized_transaction_repository,
    )
    revision = publication.revision
    advisory_diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        preparation.snapshot.revision,
        revision.casilla_values,
        modelo=preparation.work_unit.modelo,
        period_token=preparation.work_unit.period.registry_token,
        filing_year=preparation.work_unit.filing_year,
        bucket_id=preparation.work_unit.bucket_id,
        bienes_inversion_repository=ports.bienes_inversion_repository,
        observation_repository=ports.observation_repository,
        prorrata_register_repository=ports.prorrata_register_repository,
        transaction_repository=memoized_transaction_repository,
        operation=ports.operation,
        profile=preparation.profile,
    )
    profile_text_diagnostics = profile_text_casilla_gap_diagnostics(
        preparation.snapshot.revision,
        profile_fact_index(preparation.profile.record, preparation.profile.profile_decode_context.schema),
        supplied_casilla_ids=frozenset(revision.input_values_by_casilla_id),
    )
    source_diagnostics = (
        channels.reconciliation.source_diagnostics
        + channels.override_diagnostics
        + advisory_diagnostics
        + profile_text_diagnostics
    )
    # Held for the editor form until the next calculation of this declaration; those that withhold filing and
    # the activity-asset notes also persist on the revision, so a reopened declaration still shows them.
    CALCULATION_NOTES.record(revision.work_unit_id, revision.calculation_revision_id, source_diagnostics)
    return BucketAggregationCalculationResult(
        revision=revision,
        profile=preparation.profile,
        publication=publication,
        source_diagnostics=source_diagnostics,
    )


def _durable_invoice_source_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Keep explicit literal narrowing for absent invoice-source facts."""
    if diagnostic.reason == "source_domain_not_ready":
        return "source_domain_not_ready"
    if diagnostic.reason == "invoice_reverse_charge_cuota_not_derivable":
        return "invoice_reverse_charge_cuota_not_derivable"
    if diagnostic.reason == "ledger_amortization_row_unregistered":
        return "ledger_amortization_row_unregistered"
    if diagnostic.reason == "activity_asset_foral_territory":
        return "activity_asset_foral_territory"
    if diagnostic.reason == "activity_asset_residence_unresolved":
        return "activity_asset_residence_unresolved"
    return _durable_asset_note_reason(diagnostic)


def _durable_asset_note_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Keep what the calculation knew about the register with the filed record; none of these withholds anything."""
    if diagnostic.reason == "activity_asset_claim_gap":
        return "activity_asset_claim_gap"
    if diagnostic.reason == "activity_asset_accrual_unavailable":
        return "activity_asset_accrual_unavailable"
    if diagnostic.reason == "activity_asset_activity_undeclared":
        return "activity_asset_activity_undeclared"
    if diagnostic.reason == "activity_asset_agrarian_excluded":
        return "activity_asset_agrarian_excluded"
    if diagnostic.reason == "activity_asset_residence_period_unknown":
        return "activity_asset_residence_period_unknown"
    if diagnostic.reason == "activity_asset_disposal_finding":
        return "activity_asset_disposal_finding"
    if diagnostic.reason == "register_acquisition_exceeds_ledger":
        return "register_acquisition_exceeds_ledger"
    if diagnostic.reason == "register_acquisition_partly_accounted":
        return "register_acquisition_partly_accounted"
    if diagnostic.reason == "register_acquisition_row_missing":
        return "register_acquisition_row_missing"
    if diagnostic.reason == "register_owned_capital_acquisition":
        return "register_owned_capital_acquisition"
    if diagnostic.reason == "ledger_expense_may_be_durable":
        return "ledger_expense_may_be_durable"
    return None


def _durable_source_issue_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Narrow a diagnostic reason to the durable subset, or ``None``.

    Every durable reason describes a value ABSENT from the filing, which is what
    a verification or export gate reading the persisted revision needs; every
    other reason is calculate-time operator feedback that dies with the
    response. Written as explicit comparisons rather than a set membership test
    so the narrowing is one the type checker can follow — a mismatch between the
    durable set and the persisted model's own ``Literal`` then fails to compile
    instead of at the first calculation that raises the new reason.
    """
    if diagnostic.reason == "unrouted_observation":
        return "unrouted_observation"
    if diagnostic.reason == "unrouted_declarable_quantity":
        return "unrouted_declarable_quantity"
    if diagnostic.reason == "iva_selected_scope_evidence_failure":
        return "iva_selected_scope_evidence_failure"
    if diagnostic.reason == "iva_compensation_annual_source_evidence_failure":
        return "iva_compensation_annual_source_evidence_failure"
    if diagnostic.reason == "withholding_detail_absent":
        return "withholding_detail_absent"
    if diagnostic.reason == "unresolved_binding":
        return "unresolved_binding"
    if diagnostic.reason == "terminal_origin_mismatch":
        return "terminal_origin_mismatch"
    if diagnostic.reason == "unhandled_binding_source":
        return "unhandled_binding_source"
    return _durable_invoice_source_reason(diagnostic)


def _unrouted_source_issues(
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...],
    boxes: PrintedBoxes,
) -> tuple[CalculationSourceIssue, ...]:
    """Project unrouted source conditions into durable revision issues.

    The application diagnostic remains the calculate response, while the domain
    issue keeps the same source kind and actionable text available to a later
    verification/export lifecycle gate.  Provenance intentionally excludes
    these rows because no binding consumed the value they describe.

    Both unrouted reasons are carried. Projecting only the ROW condition would
    leave the quantity condition evaporating with the calculate response, so a
    later gate would see a clean persisted revision for exactly the case the
    row-keyed screens cannot report — the silence the quantity screen exists to
    break, restored one layer down.

    Every other reason that withholds filing persists the same way, so a
    reopened declaration still says what blocks it. A box whose source
    produced no value persists only when the form prints it, as ``boxes`` reads
    the published layout: a working figure that could not be worked out is worth
    checking, not a filed figure missing.
    """
    issues: list[CalculationSourceIssue] = []
    for diagnostic in source_diagnostics:
        reason = _durable_source_issue_reason(diagnostic)
        if reason is None:
            continue
        binding_source = durable_binding_source(diagnostic)
        if reason in _BINDING_SOURCE_KEYED_REASONS and binding_source is None:
            continue
        casilla_id = None if diagnostic.casilla_id is None else diagnostic.casilla_id
        if reason in PRINTED_BOX_REASONS and not boxes.prints(casilla_id):
            continue
        issues.append(
            CalculationSourceIssue(
                reason=reason,
                binding_source=binding_source,
                casilla_id=diagnostic.casilla_id,
                message=(
                    "selected-scope IVA evidence failure"
                    if reason == "iva_selected_scope_evidence_failure"
                    else diagnostic.message[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT]
                ),
                resolver_id=diagnostic.resolver_id,
                source_ref=diagnostic.source_ref,
                fact=diagnostic.fact,
            ),
        )
    return tuple(issues)


def _merge_detail_row_binding_values(
    source_binding_values: Mapping[BindingId, Decimal],
    detail_row_binding_values: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    merged = dict(source_binding_values)
    for binding_id, value in detail_row_binding_values.items():
        merged[binding_id] = merged.get(binding_id, Decimal("0")) + value
    return merged


def _reject_manual_m210_gross_income_override_in_ledger_mode(
    *,
    mode: M210GrossIncomeSourceMode | None,
    casilla_inputs: Mapping[CasillaId, Decimal],
) -> None:
    """Keep explicit ledger and manual M210 [5] authority mutually exclusive."""
    if mode is not M210GrossIncomeSourceMode.LEDGER:
        return
    if "rendimientos_integros" in casilla_inputs:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.caller_casilla_source_binding_conflict",
            context={"casillas": ["rendimientos_integros"]},
        )


def _validate_m210_official_tipo_renta_selection(
    *,
    mode: M210GrossIncomeSourceMode | None,
    m210_official_tipo_renta_code: str | None,
    text_casilla_inputs: Mapping[CasillaId, str],
) -> None:
    """Keep raw M210 code and conceptual formula token coherent at the application boundary."""
    if m210_official_tipo_renta_code is None:
        if mode is M210GrossIncomeSourceMode.LEDGER:
            raise ModeloAggregationBindingError(
                translated_message="application.modelo.errors.m210_ledger_source_selection_required",
            )
        return
    expected_tipo_renta = m210_tipo_renta_code_projection().get(m210_official_tipo_renta_code)
    if expected_tipo_renta is None or text_casilla_inputs.get("tipo_renta") != expected_tipo_renta.value:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.m210_official_tipo_renta_selection_mismatch",
            context={
                "official_tipo_renta_code": m210_official_tipo_renta_code,
                "expected_tipo_renta": expected_tipo_renta.value if expected_tipo_renta is not None else None,
                "tipo_renta": text_casilla_inputs.get("tipo_renta"),
            },
        )


def _reject_manual_m210_agrupacion_rows_in_ledger_mode(
    *,
    mode: M210GrossIncomeSourceMode | None,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Keep annual M210 ledger evidence on the same classified-row authority."""
    if mode is M210GrossIncomeSourceMode.LEDGER and any(
        isinstance(row, Modelo210AgrupacionRentaRow) for row in detail_rows
    ):
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.m210_ledger_manual_agrupacion_rows",
        )


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


#: The reason a persisted :class:`CalculationSourceIssue` may carry.
_DurableSourceIssueReason = Literal[
    "unrouted_observation",
    "unrouted_declarable_quantity",
    "iva_selected_scope_evidence_failure",
    "iva_compensation_annual_source_evidence_failure",
    "withholding_detail_absent",
    "unresolved_binding",
    "terminal_origin_mismatch",
    "unhandled_binding_source",
    "source_domain_not_ready",
    "invoice_reverse_charge_cuota_not_derivable",
    "ledger_amortization_row_unregistered",
    "activity_asset_foral_territory",
    "activity_asset_residence_unresolved",
    "activity_asset_claim_gap",
    "activity_asset_accrual_unavailable",
    "activity_asset_activity_undeclared",
    "activity_asset_agrarian_excluded",
    "activity_asset_residence_period_unknown",
    "activity_asset_disposal_finding",
    "register_acquisition_exceeds_ledger",
    "register_acquisition_partly_accounted",
    "register_acquisition_row_missing",
    "register_owned_capital_acquisition",
    "ledger_expense_may_be_durable",
]


_BINDING_SOURCE_KEYED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
    }
)
"""Reasons whose later gates select them by binding source, so an issue without one would never be read."""
