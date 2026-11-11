"""Bucket source orchestration and calculation diagnostics.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`,
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection
from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
)
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer, ValueAttestation
from ...domain.modelos.calculation_revision_sources import (
    CalculationSourceIssue,
)
from ...domain.modelos.row_models import Modelo210AgrupacionRentaRow, ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..user_profile.projections import record_to_path_values
from .action_errors import (
    ModeloAggregationInputConflictError,
)
from .calculation_action_ports import (
    CalculationActionPorts,
)
from .calculation_aggregation_context import load_bucket_aggregation_context
from .calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .calculation_modelo_adjustments import (
    calculated_decimal,
    detail_row_binding_values_for_calculation,
    union_detail_rows_by_identity,
)
from .calculation_notes import (
    CALCULATION_NOTES,
    with_element_names,
)
from .calculation_preparation import raise_if_ledger_preflight_blocks_calculation
from .calculation_publication import CalculationRevisionPublication
from .calculation_resolution import calculation_source_provenance_refs
from .calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES, CALLER_OVERRIDABLE_CARRY_SOURCES
from .calculation_source_staging import settled_binding_ids
from .m349_ledger_guard import (
    raise_if_m349_intracom_ledger_rows_need_operator_rows,
)
from .operator_override_advisory import collect_operator_override_divergence_diagnostics
from .preconditions import build_modelo_calculate_refusal_failure
from .printed_boxes import snapshot_printed_boxes
from .profile_export_binding import profile_text_casilla_gap_diagnostics, profile_text_fact_index
from .projection_unresolved import (
    ModeloProjectionUnresolvedBinding,
    ModeloProjectionUnresolvedCasilla,
    unresolved_binding_rows,
    unresolved_casilla_rows,
)
from .registry_helpers import validate_casilla_input_ids
from .transaction_catalogue_cache import MemoizedTransactionCatalogueRepository
from .work_missing_input import previous_filing_unobserved
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


from ...core.time.clock import now
from .bucket_unrouted_source_issues import unrouted_source_issues
from .calculation_actions import (
    TrustedMeshEvaluation,
    calculate_modelo_revision_with_trusted_mesh_sources,
    evaluate_modelo_revision_with_trusted_mesh_sources,
)
from .calculation_resolution import (
    operator_over_source_divergences,
    precedence_divergence_diagnostics,
    precedence_screen_context,
)
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
    unresolved_bindings: tuple[ModeloProjectionUnresolvedBinding, ...] = ()
    unresolved_casillas: tuple[ModeloProjectionUnresolvedCasilla, ...] = ()
    """The source-owned bindings and computed boxes this run left without a value, as the projection names them.

    Computed for this run only: the revision does not store them, so a reader of
    the revision alone sees the boxes absent and not why.
    """


@dataclass(frozen=True, slots=True)
class BucketAggregationPreparation:
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


@dataclass(frozen=True, slots=True)
class _CallerOverrideReconciliation:
    """Reconciliation of caller overrides against the merged source resolution.

    Carries the values the trusted-mesh calculate call and the diagnostics
    surface consume after caller ``--binding`` / ``--relation`` overrides have
    been folded into the mesh-resolved relation channel and the unresolved /
    advisory sets have been narrowed to exclude the caller-resolved ids
    (no-silent-under-declaration).
    """

    merged_relation_values: dict[RelationId, Decimal]
    unresolved_relation_ids: tuple[RelationId, ...]
    unresolved_binding_ids: tuple[BindingId, ...]
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...]
    operator_relation_values: dict[RelationId, Decimal]
    """Every relation value the operator set, through ``--relation`` or a ``--binding`` of its fold slot."""


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
        binding.id: calculated_decimal(caller_binding_values[binding.id])
        for binding, _ in relation_prefill_bindings_for_period(revision, period=target_period)
        if binding.id in caller_binding_values
    }


def orphaned_override_diagnostics(
    revision: ModeloRevision,
    *,
    caller_relation_values: Mapping[RelationId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on every relation override whose key no binding of this revision carries.

    The fold slot is the binding, so the relation channel is keyed by binding id.
    An override under any other key -- a retired relation id above all, but
    equally a typo or a key inherited from a different modelo -- is merged into
    the channel, matches nothing the engine reads, and vanishes. Vanishes is the
    operative word: the operator entered a figure, the result does not contain
    it, and nothing anywhere says so. That is a silent under-declaration whenever
    the figure would have reduced the amount owed, and it is undetectable from
    the output.

    Advisory rather than blocking. The interactive ``--relation`` surface
    already refuses an unknown key outright at the input boundary, so what
    reaches here is a PERSISTED override replayed against a revision that no
    longer declares its key -- a stored fact, not a fresh mistake, and refusing
    it would make an old catalogue entry uncalculable rather than merely
    explicable.

    ``revision`` is a :class:`ModeloRevision`.
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
    """Drop advisories whose relation or binding a caller override resolved."""
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
    unresolved binding / relation and drops its advisory.
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
    ) + orphaned_override_diagnostics(
        revision,
        caller_relation_values=caller_relation_values or {},
    )
    return _CallerOverrideReconciliation(
        merged_relation_values=merged_relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        source_diagnostics=source_diagnostics,
        operator_relation_values={**caller_relation_values_from_bindings, **dict(caller_relation_values or {})},
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


def refuse_blocked_ledger_preflight(work_unit_id: str, *, ports: CalculationActionPorts) -> None:
    """Refuse, before anything is written, a calculation the period's ledger readiness blocks.

    Calculation itself runs the same check after its preparatory writes; this
    one runs first, so a refusal the person can put right leaves no record
    changed and is reported as a refusal, not as an operation that may have
    written.
    """
    work_unit, snapshot, checked_profile = load_bucket_aggregation_context(
        work_unit_id,
        work_unit_repository=ports.work_unit_repository,
        profile=None,
        operation=ports.operation,
    )
    raise_if_ledger_preflight_blocks_calculation(
        work_unit=work_unit,
        revision=snapshot.revision,
        transaction_repository=ports.transaction_repository,
        invoice_reader=ports.invoice_catalogue_read_ports.invoice_reader,
        usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
        operation=ports.operation,
        profile_values=record_to_path_values(checked_profile.record),
    )


def refuse_empty_retenciones_window(work_unit_id: str, *, ports: CalculationActionPorts) -> None:
    """Refuse, before anything is written, a withholding period that holds no retención.

    The retenciones resolver refuses the same window during source
    resolution, which runs after the calculation's preparatory writes; this
    applies its rule first, so the person's missing answer is reported as a
    refusal with nothing changed.
    """
    from ..aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
    from ..aggregation.source_mesh import CalculationSourceContext
    from ..calculations.m115_no_relevant_payments import m115_no_relevant_payment_periods_for_bucket
    from .work_profile import ModeloWorkProfilePathValues

    work_unit, snapshot, checked_profile = load_bucket_aggregation_context(
        work_unit_id,
        work_unit_repository=ports.work_unit_repository,
        profile=None,
        operation=ports.operation,
    )
    resolver = RetencionesAggregationSourceResolver(
        ports=ports.retencion_observation_ports,
        m115_no_relevant_payment_periods=m115_no_relevant_payment_periods_for_bucket(
            work_unit.bucket_id,
            profile_path_values_reader=ModeloWorkProfilePathValues(profile=checked_profile),
        ),
        invoice_catalogue=ports.invoice_catalogue_read_ports,
    )
    refusal = resolver.empty_window_refusal(
        CalculationSourceContext(
            bucket_id=work_unit.bucket_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision=snapshot.revision,
            profile=checked_profile,
            operation=ports.operation,
        )
    )
    if refusal is not None:
        raise refusal


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
) -> BucketAggregationPreparation:
    """Load, validate, and protect caller channels before source resolution."""
    work_unit, snapshot, checked_profile = load_bucket_aggregation_context(
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
        subject_leaf_key="modelo.work.calculate",
    )
    return BucketAggregationPreparation(
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
    for casilla_id, value in validate_casilla_input_ids(snapshot.revision, casilla_inputs).items():
        validated_inputs[casilla_id] = _require_decimal_input(value)
    return validated_inputs


def _require_decimal_input(value: object) -> Decimal:
    """Keep the source-mesh contract concrete at the engine boundary."""
    if not isinstance(value, Decimal):
        raise TypeError(f"validated casilla input is not a Decimal: {value!r}")
    return value


def resolve_bucket_aggregation_source_resolution(
    *,
    preparation: BucketAggregationPreparation,
    ports: CalculationActionPorts,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...],
    foreign_asset_row_observations: tuple[Modelo720RowObservation, ...],
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    m210_official_tipo_renta_code: str | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    filing_period_date: date | None,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    income_family_entry_digests: Mapping[str, str] | None = None,
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
        income_family_entry_digests=income_family_entry_digests,
    )
    reject_caller_overrides_of_source_bindings(
        revision=preparation.snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources) - CALLER_OVERRIDABLE_CARRY_SOURCES,
        caller_binding_values=preparation.binding_values,
        caller_casilla_inputs=preparation.casilla_inputs,
        caller_enum_binding_values=enum_binding_values,
        closed_record_row_sets=source_resolution.closed_record_row_sets,
        source_supplied_binding_ids=frozenset(source_resolution.binding_values)
        | frozenset(source_resolution.enum_binding_values),
        subject_leaf_key="modelo.work.calculate",
    )
    return source_resolution


def _bucket_aggregation_channels(
    *,
    preparation: BucketAggregationPreparation,
    operation: PinnedAuthorityOperation,
    source_resolution: CalculationSourceResolution,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> _BucketAggregationChannels:
    """Compose mesh, detail-row, and caller channels in their established order."""
    all_detail_rows = union_detail_rows_by_identity(
        resolver_rows=source_resolution.detail_rows,
        caller_rows=detail_rows,
    )
    raise_if_m349_intracom_ledger_rows_need_operator_rows(
        work_unit=preparation.work_unit,
        transaction_repository=transaction_repository,
        detail_rows=all_detail_rows,
    )
    detail_row_binding_values = detail_row_binding_values_for_calculation(
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
    reconciliation = _reconcile_caller_overrides(
        revision=preparation.snapshot.revision,
        target_period=preparation.work_unit.period.registry_token,
        source_resolution=source_resolution,
        caller_binding_values=preparation.binding_values,
        caller_relation_values=preparation.relation_values,
        detail_row_binding_values=detail_row_binding_values,
    )
    screen_diagnostics = _operator_over_source_diagnostics(
        preparation,
        operation=operation,
        source_relations=source_resolution.relation_values,
        operator_relations={
            # A fold slot the operator set by ``--binding`` over a binding the mesh also
            # resolved is compared once, in the binding overlay, not again as a relation.
            relation_id: value
            for relation_id, value in reconciliation.operator_relation_values.items()
            if relation_id in preparation.relation_values or relation_id not in backend_binding_values
        },
        source_casillas=backend_source_inputs,
    )
    filing_bound_boxes = frozenset(
        diagnostic.casilla_id
        for diagnostic in screen_diagnostics
        if diagnostic.casilla_id is not None and diagnostic.relation_id is None
    )
    override_diagnostics = tuple(
        diagnostic
        for diagnostic in collect_operator_override_divergence_diagnostics(
            preparation.snapshot.revision,
            casilla_inputs=preparation.casilla_inputs,
            bound_inputs=backend_source_inputs,
        )
        if diagnostic.casilla_id not in filing_bound_boxes
    )
    return _BucketAggregationChannels(
        source_resolution=source_resolution,
        detail_rows=all_detail_rows,
        backend_binding_values=backend_binding_values,
        backend_casilla_inputs=backend_casilla_inputs,
        override_diagnostics=override_diagnostics,
        reconciliation=replace(
            reconciliation, source_diagnostics=reconciliation.source_diagnostics + screen_diagnostics
        ),
    )


def _operator_over_source_diagnostics(
    preparation: BucketAggregationPreparation,
    *,
    operation: PinnedAuthorityOperation,
    source_relations: Mapping[RelationId, Decimal],
    operator_relations: Mapping[RelationId, Decimal],
    source_casillas: Mapping[CasillaId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """The divergences between the operator's relations and boxes and the mesh's, that a filer must see.

    A box that reaches no exported box keeps the operator-override advisory
    the merge always raised, so only its filing-bound divergence is kept here;
    a relation's divergence is kept either way.
    """
    divergences = operator_over_source_divergences(
        source_relations=source_relations,
        operator_relations=operator_relations,
        source_casillas=source_casillas,
        operator_casillas=preparation.casilla_inputs,
    )
    if not divergences:
        return ()
    diagnostics = precedence_divergence_diagnostics(
        divergences, screen=precedence_screen_context(preparation.work_unit, preparation.snapshot, operation=operation)
    )
    return tuple(diagnostic for diagnostic in diagnostics if diagnostic.reason != _OPERATOR_OVERRIDE_ADVISORY_REASON)


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
    preparation: BucketAggregationPreparation,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    attested_binding_ids: tuple[BindingId, ...],
    value_attestations: Mapping[BindingId, ValueAttestation],
    income_family_entry_digests: Mapping[str, str],
) -> CalculationOperatorLayer:
    """Project the validated caller tier of one run onto the persisted operator layer.

    Only the caller channels are read: the backend, bound, profile and borrador
    tiers merged into the revision's replay maps never reach the layer, so a
    later replay cannot promote a source value into an operator override. The
    overrides the operator stated hold nothing stay marked as that statement.
    """
    return CalculationOperatorLayer(
        decimal_casilla_inputs={
            casilla_id: canonical_decimal_string(value) for casilla_id, value in preparation.casilla_inputs.items()
        },
        text_casilla_inputs=dict(text_casilla_inputs or {}),
        binding_overrides={
            **{binding_id: canonical_decimal_string(value) for binding_id, value in preparation.binding_values.items()},
            **dict(enum_binding_values or {}),
        },
        attested_binding_ids=attested_binding_ids,
        value_attestations=dict(value_attestations),
        income_family_entry_digests=dict(income_family_entry_digests),
    )


def _bucket_aggregation_source_diagnostics(
    *,
    preparation: BucketAggregationPreparation,
    channels: _BucketAggregationChannels,
    precedence_diagnostics: tuple[CalculationSourceDiagnostic, ...],
    profile_diagnostics: tuple[CalculationSourceDiagnostic, ...],
    revision: CalculationRevision,
    ports: CalculationActionPorts,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Join the mesh, precedence, override, advisory and profile-text diagnostics a calculation reports."""
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
        transaction_repository=transaction_repository,
        invoice_reader=ports.invoice_catalogue_read_ports.invoice_reader,
        operation=ports.operation,
        profile=preparation.profile,
    )
    profile_text_diagnostics = profile_text_casilla_gap_diagnostics(
        preparation.snapshot.revision,
        profile_text_fact_index(
            preparation.profile.record,
            preparation.profile.profile_decode_context.schema,
            operation=ports.operation,
        ),
        supplied_casilla_ids=frozenset(revision.input_values_by_casilla_id),
        derived_selectors=preparation.profile.profile_decode_context.schema.derived_selectors,
    )
    source_diagnostics = (
        channels.reconciliation.source_diagnostics
        + precedence_diagnostics
        + profile_diagnostics
        + channels.override_diagnostics
        + advisory_diagnostics
        + profile_text_diagnostics
        + credit_reconciliation_diagnostics(revision.source_issues)
    )
    return with_element_names(source_diagnostics, ports.activity_asset_history_repository)


def calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    record_operator_layer: bool = False,
    attested_binding_ids: tuple[BindingId, ...] = (),
    value_attestations: Mapping[BindingId, ValueAttestation] | None = None,
    income_family_entry_digests: Mapping[str, str] | None = None,
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
    run = _resolve_bucket_aggregation_run(
        work_unit_id,
        ports=ports,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
        foreign_asset_observations=foreign_asset_observations,
        foreign_asset_row_observations=foreign_asset_row_observations,
        detail_rows=detail_rows,
        profile=profile,
        income_family_entry_digests=income_family_entry_digests or {},
    )
    preparation = run.preparation
    printed = snapshot_printed_boxes(ports.operation, preparation.snapshot)
    memoized_transaction_repository = run.transaction_repository
    channels = run.channels
    calculation = calculate_modelo_revision_with_trusted_mesh_sources(
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
                attested_binding_ids=attested_binding_ids,
                value_attestations=value_attestations or {},
                income_family_entry_digests=income_family_entry_digests or {},
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
        payment_year_binding_values=channels.source_resolution.payment_year_binding_values,
        instalment_basis_binding_values=channels.source_resolution.instalment_basis_binding_values,
        closed_record_row_sets=channels.source_resolution.closed_record_row_sets,
        row_casilla_values=channels.source_resolution.row_casilla_values,
        row_casilla_provenance=channels.source_resolution.row_casilla_provenance,
        backend_casilla_inputs=channels.backend_casilla_inputs,
        iva_compensation_decision=iva_compensation_decision,
        enum_binding_values=_run_enum_binding_values(run, enum_binding_values),
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=channels.reconciliation.merged_relation_values,
        unresolved_relation_ids=channels.reconciliation.unresolved_relation_ids,
        unresolved_binding_ids=channels.reconciliation.unresolved_binding_ids,
        settled_binding_ids=settled_binding_ids(channels.source_resolution),
        source_transaction_ids=tuple(channels.source_resolution.source_transaction_ids),
        source_provenance=calculation_source_provenance_refs(channels.source_resolution.provenance),
        source_issues=unrouted_source_issues(
            channels.reconciliation.source_diagnostics,
            printed,
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
    publication = calculation.publication
    revision = publication.revision
    source_diagnostics = _bucket_aggregation_source_diagnostics(
        preparation=preparation,
        channels=channels,
        precedence_diagnostics=calculation.precedence_diagnostics,
        profile_diagnostics=calculation.profile_diagnostics,
        revision=revision,
        ports=ports,
        transaction_repository=memoized_transaction_repository,
    )
    # Held for the editor form until the next calculation of this declaration; those that withhold filing and
    # the activity-asset notes also persist on the revision, so a reopened declaration still shows them.
    CALCULATION_NOTES.record(revision.work_unit_id, revision.calculation_revision_id, source_diagnostics)
    return BucketAggregationCalculationResult(
        revision=revision,
        profile=preparation.profile,
        publication=publication,
        source_diagnostics=source_diagnostics,
        unresolved_bindings=unresolved_binding_rows(
            # The engine reads a settled binding (inapplicable to the filer, or answered on the row channel)
            # as a source that answered, so it is not a gap.
            tuple(
                binding_id
                for binding_id in channels.reconciliation.unresolved_binding_ids
                if binding_id not in settled_binding_ids(channels.source_resolution)
            ),
            channels.reconciliation.source_diagnostics,
            preparation.snapshot.revision,
            printed,
            typed_casilla_ids=preparation.casilla_inputs.keys(),
        ),
        unresolved_casillas=unresolved_casilla_rows(calculation.engine_result, preparation.snapshot.revision, printed),
    )


def evaluate_modelo_revision_from_bucket_aggregation(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    clock: datetime | None = None,
    profile: ModeloWorkProfile | None = None,
) -> TrustedMeshEvaluation:
    """Evaluate a declaration from its bucket sources exactly as a calculation would, publishing nothing.

    The same source mesh, caller reconciliation, preparation gates and engine
    run that :func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
    publishes, for a reader that needs the answer of a calculation it must
    not save: no revision, event or migration is written. ``profile`` is the
    record every gate and resolver reads, so a caller can evaluate the
    declaration under a profile it holds only in memory.
    """
    run = _resolve_bucket_aggregation_run(
        work_unit_id,
        ports=ports,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
        foreign_asset_observations=(),
        foreign_asset_row_observations=(),
        detail_rows=detail_rows,
        profile=profile,
    )
    channels = run.channels
    return evaluate_modelo_revision_with_trusted_mesh_sources(
        work_unit_id,
        ports=ports,
        evaluated_at=clock or now(),
        casilla_inputs=run.preparation.casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        cleared_casilla_ids=cleared_casilla_ids,
        binding_values=run.preparation.binding_values,
        enum_binding_values=_run_enum_binding_values(run, enum_binding_values),
        backend_binding_values=channels.backend_binding_values,
        row_binding_values=channels.source_resolution.row_binding_values,
        closed_record_row_sets=channels.source_resolution.closed_record_row_sets,
        backend_casilla_inputs=channels.backend_casilla_inputs,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=channels.reconciliation.merged_relation_values,
        unresolved_relation_ids=channels.reconciliation.unresolved_relation_ids,
        unresolved_binding_ids=channels.reconciliation.unresolved_binding_ids,
        settled_binding_ids=settled_binding_ids(channels.source_resolution),
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        filing_period_date=filing_period_date,
        detail_rows=channels.detail_rows,
        source_provenance=calculation_source_provenance_refs(channels.source_resolution.provenance),
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=(
            channels.source_resolution.m303_regimen_simplificado_annual_summary_handoff
        ),
        profile=run.preparation.profile,
    )


@dataclass(frozen=True, slots=True)
class _BucketAggregationRun:
    """The validated caller channels and the mesh-derived channels of one calculation, before the engine runs."""

    preparation: BucketAggregationPreparation
    channels: _BucketAggregationChannels
    transaction_repository: MemoizedTransactionCatalogueRepository


def _run_enum_binding_values(
    run: _BucketAggregationRun, enum_binding_values: Mapping[BindingId, str] | None
) -> dict[BindingId, str]:
    """The source enum bindings with the caller's own values winning."""
    return {**dict(run.channels.source_resolution.enum_binding_values), **dict(enum_binding_values or {})}


def _resolve_bucket_aggregation_run(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    m210_official_tipo_renta_code: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
    binding_values: Mapping[BindingId, Decimal] | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    relation_values: Mapping[RelationId, Decimal] | None,
    filing_period_date: date | None,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...],
    foreign_asset_row_observations: tuple[Modelo720RowObservation, ...],
    detail_rows: tuple[ModeloDetailRow, ...],
    profile: ModeloWorkProfile | None,
    income_family_entry_digests: Mapping[str, str] | None = None,
) -> _BucketAggregationRun:
    """Validate the caller channels, resolve the source mesh and reconcile the two."""
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
    # Share contributor reads between the source mesh and the ledger snapshot anchor.
    memoized_transaction_repository = MemoizedTransactionCatalogueRepository(ports.transaction_repository)
    raise_if_ledger_preflight_blocks_calculation(
        work_unit=preparation.work_unit,
        revision=preparation.snapshot.revision,
        transaction_repository=memoized_transaction_repository,
        invoice_reader=ports.invoice_catalogue_read_ports.invoice_reader,
        usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
        operation=ports.operation,
        profile_values=record_to_path_values(preparation.profile.record),
    )
    try:
        source_resolution = resolve_bucket_aggregation_source_resolution(
            preparation=preparation,
            ports=ports,
            foreign_asset_observations=foreign_asset_observations,
            foreign_asset_row_observations=foreign_asset_row_observations,
            text_casilla_inputs=text_casilla_inputs,
            m210_official_tipo_renta_code=m210_official_tipo_renta_code,
            enum_binding_values=enum_binding_values,
            filing_period_date=filing_period_date,
            transaction_repository=memoized_transaction_repository,
            income_family_entry_digests=income_family_entry_digests,
        )
    except RegistryValidationError as error:
        # A stored earlier return that does not show the boxes a carry reads is
        # answered by the operator stating the carry, where the edit admits it.
        snapshot = preparation.snapshot
        refusal = previous_filing_unobserved(
            error,
            work_unit=preparation.work_unit,
            snapshot=snapshot,
            boxes=snapshot_printed_boxes(ports.operation, snapshot),
            layout=ports.operation.form_layout(str(preparation.work_unit.modelo), snapshot.revision.id),
        )
        if refusal is None:
            raise
        raise refusal from error
    channels = _bucket_aggregation_channels(
        preparation=preparation,
        operation=ports.operation,
        source_resolution=source_resolution,
        transaction_repository=memoized_transaction_repository,
        detail_rows=detail_rows,
    )
    return _BucketAggregationRun(
        preparation=preparation, channels=channels, transaction_repository=memoized_transaction_repository
    )


_CREDIT_RECONCILIATION_REASONS: Final[frozenset[str]] = frozenset(
    {"credit_source_disagreement", "credit_cross_check_absent", "credit_resolution_stale"},
)


def credit_reconciliation_diagnostics(
    issues: tuple[CalculationSourceIssue, ...],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Restate the credit reconciliation's persisted findings as this calculation's notes.

    The comparison runs on the calculated values, inside the calculation, so its
    findings are persisted before any note is shown; the notes say the same.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason=_credit_reconciliation_reason(issue),
            source_kind="credit_reconciliation",
            binding_source=issue.binding_source,
            casilla_id=issue.casilla_id,
            message=issue.message,
            source_ref=issue.source_ref,
            fact=issue.fact,
            disagreement=issue.disagreement,
        )
        for issue in issues
        if issue.reason in _CREDIT_RECONCILIATION_REASONS
    )


def _credit_reconciliation_reason(
    issue: CalculationSourceIssue,
) -> Literal["credit_source_disagreement", "credit_cross_check_absent", "credit_resolution_stale"]:
    if issue.reason == "credit_source_disagreement":
        return "credit_source_disagreement"
    if issue.reason == "credit_resolution_stale":
        return "credit_resolution_stale"
    return "credit_cross_check_absent"


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
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.caller_casilla_source_binding_conflict",
            context={"casillas": ["rendimientos_integros"]},
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="m210.gross_income_source.ledger_with_manual_gross_income",
                evidence_values={"rejected_casilla_ids": "rendimientos_integros", "ledger_source": True},
            ),
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
            raise ModeloAggregationInputConflictError(
                translated_message="application.modelo.errors.m210_ledger_source_selection_required",
                precondition_failure=build_modelo_calculate_refusal_failure(
                    scenario="m210.tipo_renta.ledger_selection_missing",
                    evidence_values={"ledger_source": True, "official_tipo_renta_code_stated": False},
                ),
            )
        return
    expected_tipo_renta = m210_tipo_renta_code_projection().get(m210_official_tipo_renta_code)
    if expected_tipo_renta is None or text_casilla_inputs.get("tipo_renta") != expected_tipo_renta.value:
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.m210_official_tipo_renta_selection_mismatch",
            context={
                "official_tipo_renta_code": m210_official_tipo_renta_code,
                "expected_tipo_renta": expected_tipo_renta.value if expected_tipo_renta is not None else None,
                "tipo_renta": text_casilla_inputs.get("tipo_renta"),
            },
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="m210.tipo_renta.official_code_mismatch",
                evidence_values={
                    "official_tipo_renta_code": m210_official_tipo_renta_code,
                    "official_code_recognised": expected_tipo_renta is not None,
                },
            ),
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
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.m210_ledger_manual_agrupacion_rows",
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="m210.gross_income_source.ledger_with_manual_agrupacion_rows",
                evidence_values={
                    "ledger_source": True,
                    "manual_agrupacion_row_count": sum(
                        isinstance(row, Modelo210AgrupacionRentaRow) for row in detail_rows
                    ),
                },
            ),
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
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.computed_casilla_binding_conflict",
            context={"computed": computed},
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="bound_inputs.computed_casilla_bound",
                evidence_values={"computed_casilla_count": len(computed), "computed_casilla_ids": "|".join(computed)},
            ),
        )
    return dict(sorted({**bound_inputs, **casilla_inputs}.items()))


_OPERATOR_OVERRIDE_ADVISORY_REASON: Final = "operator_override_diverges_from_computed"
"""The advisory a box the operator set keeps where it reaches no exported box."""


"""Reasons whose later gates select them by binding source, so an issue without one would never be read."""
