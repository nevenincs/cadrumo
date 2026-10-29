"""Calculation revision actions for modelo work units.

The calculate paths resolve a law-determined :class:`~domain.calculations.registry.schema.RegistrySnapshot` from
each :class:`~WorkUnit`, merge manual inputs with profile,
borrador, IVA-wallet, and bucket aggregation channels, and execute
:func:`~domain.calculations.registry.formula_runtime.calculate_registry_snapshot` against
the asserted :class:`~domain.calculations.registry.schema.ModeloRevision`.

Persistence is centralized through :class:`~CalculationRevision` and the
application-owned :class:`~.calculation_action_ports.CalculationActionPorts`,
so the work-unit pointer and
``modelo.calculation.created`` event advance with the stored draft revision.

:func:`~application.modelo.calculation_actions.calculate_modelo_revision` is the lower-level
calculation service: callers provide already-resolved manual, binding,
enum-binding, relation, borrador, and IVA-wallet inputs.
:func:`~application.modelo.calculation_bucket_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
first runs the application source mesh over bucket-local ledgers, invoices,
previous filings, relation prefill, retenciones, withholding, and detail rows,
then feeds the resolved backend channels into the same persistence path. It is
the only entry point into that orchestration, and it returns the non-blocking
source diagnostics with the revision rather than beside it, so no caller can
reach the mesh and lose the advisories on the way out.
Source-owned bindings and their bound casillas are guarded before the engine
runs so a persisted revision cannot claim bucket-source grounding while carrying
a caller substitute for the same value.

See Also:
    :mod:`~application.aggregation`:
        Public source-mesh contracts and diagnostics consumed by the bucket
        aggregation path.
    :func:`~application.modelo.calculation_resolution.resolve_calculation_binding_channels`:
        Merges caller, backend, borrador, and date binding channels for the
        registry engine.
    :func:`~application.modelo._calculation_helpers.build_typed_observations`:
        Projects engine output into provenance-bearing casilla observations.
    :func:`~application.modelo.revision_persistence.persist_calculation_revision`:
        Stores the content-addressed ``BORRADOR`` revision and emits the bucket
        event.
    :func:`~application.modelo.verification_actions.verify_modelo_revision_with_preconditions`:
        Lifecycle gate that promotes a calculated revision after verification.

Core types:
:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.time.clock import now as _utc_now
from ...domain.calculations.record_row_membership import ClosedRecordRowSet
from ...domain.calculations.registry.casilla_membership import reject_row_field_template_scalar_inputs
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.formula_runtime import (
    RegistryCalculationResult,
    calculate_registry_snapshot,
)
from ...domain.calculations.registry.formula_text_inputs import validated_text_input_casilla_ids
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ...domain.calculations.row_source_identity import RowBindingKey, RowSourceIdentity
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303RegimenSimplificadoAnnualSummaryHandoff,
)
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from ...domain.modelos.calculation_revision_sources import CalculationSourceIssue, CalculationSourceRef
from ...domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.projections import profile_fact_index
from ._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)
from ._calculation_modelo_adjustments import (
    drop_row_field_template_outputs as _drop_row_field_template_outputs,
)
from ._calculation_modelo_adjustments import (
    m131_objective_estimation_data_base_inputs as _m131_objective_estimation_data_base_inputs,
)
from ._calculation_modelo_adjustments import (
    raise_if_m390_303_reconciliation_would_save_silent_zero as _raise_if_m390_303_reconciliation_would_save_silent_zero,
)
from ._calculation_modelo_adjustments import (
    require_detail_rows_declared_for_their_owning_modelo as _require_detail_rows_declared_for_their_owning_modelo,
)
from ._calculation_preparation import PreparedCalculation as _PreparedCalculation
from ._calculation_preparation import prepare_calculation as _prepare_calculation
from .action_errors import (
    ModeloClearedCasillaSourceFedError,
)
from .calculation_action_ports import (
    CalculationActionPorts,
)
from .calculation_publication import CalculationRevisionPublication
from .calculation_resolution import build_calculation_replay_payloads as _build_calculation_replay_payloads
from .calculation_resolution import resolve_calculation_inputs as _resolve_calculation_inputs
from .m123_count_authority_gate import Modelo123CountAuthorityStage, require_modelo_123_count_authority
from .m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision
from .profile_export_binding import resolve_profile_text_casilla_inputs
from .revision_persistence import persist_calculation_revision
from .work_missing_input import ModeloWorkMissingInputError
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...core.secure_object_write import SecureObjectWrite
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.bindings import CasillaObservation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from .calculation_resolution import CalculationReplayPayloads


from .calculation_source_guards import (
    m210_gross_source_mode,
    require_m303_regimen_simplificado_annual_summary_arrival_values,
    require_m303_regimen_simplificado_annual_summary_handoff,
    validate_m210_agrupacion_renta_detail_rows,
)


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal],
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    source_transaction_ids: tuple[str, ...] = (),
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    filing_period_date: date | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Run the registry formula engine, persist a draft revision, and return a :class:`CalculationRevision`.

    This public service accepts operator and application calculation inputs only.
    Source-mesh provenance and unresolved-source issues are established solely
    by the private mesh bridge below; callers cannot manufacture the M369
    OSS/IOSS source-assessment record used by verification and export.

    Args:
        work_unit_id: Identifier of the filing work unit to calculate.
        actor: Audit actor recorded on the persisted calculation revision.
        casilla_inputs: Operator-supplied numeric values keyed by casilla.
        text_casilla_inputs: Optional operator-supplied text values keyed by casilla.
        binding_values: Optional numeric overrides for registry bindings.
        enum_binding_values: Optional enumerated registry-binding values.
        backend_binding_values: Optional binding values resolved by backend authorities.
        row_binding_values: Optional detail-row binding values keyed by binding and row.
        backend_casilla_inputs: Optional casilla values resolved by backend authorities.
        iva_compensation_decision: Optional IVA compensation election for this calculation.
        ports: Required application-owned persistence capabilities for this
            calculation and its source mesh.
        borrador_snapshot_id: Optional Modelo 100 draft snapshot selected as input.
        relation_values: Optional numeric overrides for declared registry relations.
        unresolved_relation_ids: Relations that source resolution could not satisfy.
        unresolved_binding_ids: Bindings that source resolution could not satisfy.
        source_transaction_ids: Ledger transactions contributing to the calculation.
        m210_official_tipo_renta_code: Optional official Modelo 210 income-type code.
        m210_gross_income_source_mode: Selected Modelo 210 gross-income source authority.
        filing_period_date: Date used to resolve the applicable filing period.
        detail_rows: Repeating detail rows supplied to the registry engine.
        filing_instance_evidence: Immutable operator-selected Modelo 303 filing facts.
        clock: Optional deterministic timestamp for the persisted revision.

    """
    return calculate_modelo_revision_with_trusted_mesh_sources(
        work_unit_id,
        ports=ports,
        actor=actor,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        backend_binding_values=backend_binding_values,
        row_binding_values=row_binding_values,
        row_source_identities=None,
        closed_record_row_sets=(),
        backend_casilla_inputs=backend_casilla_inputs,
        iva_compensation_decision=iva_compensation_decision,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        source_transaction_ids=source_transaction_ids,
        source_provenance=(),
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        filing_period_date=filing_period_date,
        detail_rows=detail_rows,
        filing_instance_evidence=filing_instance_evidence,
        source_issues=(),
        clock=clock,
        profile=None,
    ).revision


def _draft_ledger_anchor(
    *,
    work_unit: WorkUnit,
    source_transaction_ids: tuple[str, ...],
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    captured_at: datetime,
) -> LedgerFilingSnapshot | None:
    """Return the ledger snapshot this calculation consumed, or ``None``.

    Pins the ledger state these casilla values were computed FROM, so verify can
    later detect that the contributing rows moved underneath a draft. Without it
    a draft has no anchor at all: the snapshot is otherwise captured only on a
    granted verify, which is exactly the drafts that need guarding.

    The anchor for the verify-time drift gate. A ledger-derived draft records
    the fingerprints of the rows its casilla values were computed from, so a
    later verify can tell whether those rows still say what they said. The
    fingerprint covers tax facts only — amount, classification, taxable base,
    IVA and IRPF category, lifecycle state — so it moves when a reclassify
    invalidates the computed values and stays put when an evidence attach does
    not. That discrimination is what lets the gate refuse a stale draft without
    refusing the attach-and-re-verify recovery.

    Returns ``None`` for a revision with no contributing rows: nothing can
    drift under it, and storing an empty snapshot would only add noise.
    """
    if not source_transaction_ids:
        return None
    from ..aggregation.ledger_filing_snapshot import compute_ledger_filing_snapshot

    return compute_ledger_filing_snapshot(
        source_transaction_ids=source_transaction_ids,
        catalogue=transaction_repository.load_by_ids(source_transaction_ids),
        captured_at=captured_at,
    )


def _optional_mapping_as_dict[OptionalMappingKey, OptionalMappingValue](
    value: Mapping[OptionalMappingKey, OptionalMappingValue] | None,
) -> dict[OptionalMappingKey, OptionalMappingValue]:
    """Materialize an optional action payload with its historical defaults."""
    return dict(value or {})


def _trusted_backend_casilla_inputs(
    *,
    prepared: _PreparedCalculation,
    work_unit: WorkUnit,
    revision: ModeloRevision,
) -> dict[CasillaId, Decimal]:
    """Combine registry-derived M131 inputs with prepared backend inputs."""
    return {
        **_m131_objective_estimation_data_base_inputs(
            work_unit=work_unit,
            revision=revision,
            binding_values=prepared.channels.bindings,
        ),
        **dict(prepared.backend_casilla_inputs or dict[CasillaId, Decimal]()),
    }


def _trusted_calculation_clock(clock: datetime | None) -> datetime:
    """Resolve the timestamp shared by ledger anchoring and persistence."""
    return clock or _utc_now()


def calculate_modelo_revision_with_trusted_mesh_sources(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal],
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    operator_layer: CalculationOperatorLayer | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None = None,
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] | None = None,
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
    row_casilla_values: Mapping[RowCasillaKey, Decimal] | None = None,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    source_transaction_ids: tuple[str, ...] = (),
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    filing_period_date: date | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    source_provenance: tuple[CalculationSourceRef, ...],
    source_issues: tuple[CalculationSourceIssue, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    clock: datetime | None = None,
    additional_secure_object_writes_for_revision: (
        Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None
    ) = None,
    profile: ModeloWorkProfile | None,
) -> CalculationRevisionPublication:
    """Calculate and persist a revision using trusted source evidence."""
    ports.relation_override_migration.migrate(ports.calculation_repository, operation=ports.operation)
    now = _trusted_calculation_clock(clock)
    prepared = _prepare_calculation(
        evaluated_at=now,
        work_unit_id=work_unit_id,
        work_unit_repository=ports.work_unit_repository,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        ledger_preflight_transaction_repository=ports.transaction_repository,
        usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
        operation=ports.operation,
        iva_compensation_decision=iva_compensation_decision,
        observation_repository=ports.observation_repository,
        iva_compensation_decision_repository=ports.iva_compensation_decision_repository,
        iva_compensation_history_repository=ports.iva_compensation_history_repository,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        backend_binding_values=backend_binding_values,
        filing_period_date=filing_period_date,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=ports.borrador_snapshot_repository,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        profile=profile,
    )
    work_units = prepared.work_units
    work_unit = prepared.work_unit
    snapshot = prepared.snapshot
    (
        engine_result,
        replay_payloads,
        casilla_values,
        typed_observations,
        validated_filing_instance_evidence,
        resolved_text_inputs,
    ) = _evaluate_prepared_calculation(
        prepared,
        ports,
        detail_rows,
        m210_official_tipo_renta_code,
        relation_values,
        text_casilla_inputs,
        cleared_casilla_ids,
        unresolved_relation_ids,
        unresolved_binding_ids,
        closed_record_row_sets,
        row_binding_values,
        filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff,
    )

    return persist_calculation_revision(
        operation=ports.operation,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        rendering_snapshot=_capture_calculation_rendering(snapshot, operation=ports.operation),
        work_unit=work_unit,
        work_units=work_units,
        work_units_revision_id=prepared.work_units_revision_id,
        ledger_filing_snapshot=_draft_ledger_anchor(
            work_unit=work_unit,
            source_transaction_ids=source_transaction_ids,
            transaction_repository=(
                transaction_repository if transaction_repository is not None else ports.transaction_repository
            ),
            captured_at=now,
        ),
        input_values_by_casilla_id={**replay_payloads.input_values_by_casilla_id, **resolved_text_inputs},
        binding_overrides=replay_payloads.binding_overrides,
        row_binding_values=replay_payloads.row_binding_values,
        row_source_identities=_optional_mapping_as_dict(row_source_identities),
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=_optional_mapping_as_dict(row_casilla_values),
        row_casilla_provenance=_optional_mapping_as_dict(row_casilla_provenance),
        relation_overrides=replay_payloads.relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_source_mode(work_unit, m210_gross_income_source_mode),
        borrador_snapshot_id=prepared.channels.borrador_snapshot_id,
        bindings_sourced_from_borrador=prepared.channels.bindings_sourced_from_borrador,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        observations=typed_observations,
        unresolved_outcomes=engine_result.unresolved_outcomes,
        source_provenance=source_provenance,
        source_issues=source_issues,
        filing_instance_evidence=validated_filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        detail_rows=detail_rows,
        formula_count=len(engine_result.entries),
        actor=actor,
        now=now,
        calculation_repository=ports.calculation_repository,
        work_unit_repository=ports.work_unit_repository,
        bucket_event_repository=ports.bucket_event_repository,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )


def _reject_clears_of_source_fed_casillas(
    cleared_casilla_ids: tuple[CasillaId, ...],
    *,
    resolved_casilla_ids: tuple[CasillaId, ...],
) -> None:
    """Refuse an explicit clear that a source would immediately refill.

    A caller never supplies a value for a casilla it clears, so a cleared
    casilla that still reaches the resolved inputs was fed by a source tier.
    Persisting the clear would record "cleared" beside the source's value for
    the same casilla -- two contradictory facts about one box.
    """
    fed = sorted(set(cleared_casilla_ids).intersection(resolved_casilla_ids))
    if fed:
        raise ModeloClearedCasillaSourceFedError(
            translated_message="errors.error.error_modelo_cleared_casilla_source_fed",
            context={"casilla_ids": ",".join(fed)},
        )


def _capture_calculation_rendering(
    snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation
) -> CalculationRenderingSnapshot:
    """Join the separately published form under the actual calculation's leased pin."""
    layout = operation.form_layout(snapshot.modelo.id, snapshot.revision.id)
    if layout is not None:
        snapshot = snapshot.model_copy(
            update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
        )
    return CalculationRenderingSnapshot.capture(snapshot, authority_generation=operation.pin().logical_generation)


def _calculate_prepared_registry_snapshot(
    snapshot: RegistrySnapshot,
    *,
    resolved_inputs: Mapping[CasillaId, Decimal],
    resolved_text_inputs: Mapping[CasillaId, str],
    period_date: date,
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str],
    relation_values: Mapping[RelationId, Decimal],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
    date_binding_values: Mapping[BindingId, date],
    boolean_binding_values: Mapping[BindingId, bool],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
) -> RegistryCalculationResult:
    """Evaluate the registry after application channels have been resolved."""
    return calculate_registry_snapshot(
        snapshot,
        inputs=resolved_inputs,
        text_inputs=resolved_text_inputs or None,
        date_context={"filing_period": period_date},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        date_binding_values=date_binding_values or None,
        boolean_binding_values=boolean_binding_values or None,
        closed_record_row_sets=closed_record_row_sets,
    )


def _evaluate_prepared_calculation(
    prepared: _PreparedCalculation,
    ports: CalculationActionPorts,
    detail_rows: tuple[ModeloDetailRow, ...],
    m210_official_tipo_renta_code: str | None,
    relation_values: Mapping[RelationId, Decimal] | None,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    cleared_casilla_ids: tuple[CasillaId, ...],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...],
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None,
    filing_instance_evidence: FilingInstanceEvidence | None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
) -> tuple[
    RegistryCalculationResult,
    CalculationReplayPayloads,
    dict[CasillaId, Decimal],
    tuple[CasillaObservation, ...],
    FilingInstanceEvidence | None,
    Mapping[CasillaId, str],
]:
    """Evaluate the pinned snapshot and validate its publication evidence."""
    work_unit = prepared.work_unit
    snapshot = prepared.snapshot
    require_modelo_123_count_authority(
        work_unit,
        retencion_ports=ports.retencion_observation_ports,
        stage=Modelo123CountAuthorityStage.CALCULATE,
    )
    require_m303_regimen_simplificado_annual_summary_handoff(
        revision=snapshot.revision,
        profile=prepared.profile,
        handoff=m303_regimen_simplificado_annual_summary_handoff,
    )
    _require_detail_rows_declared_for_their_owning_modelo(work_unit=work_unit, detail_rows=detail_rows)
    validate_m210_agrupacion_renta_detail_rows(work_unit, detail_rows, m210_official_tipo_renta_code)
    resolved_relations = _optional_mapping_as_dict(relation_values)
    backend_casilla_inputs = _trusted_backend_casilla_inputs(
        prepared=prepared,
        work_unit=work_unit,
        revision=snapshot.revision,
    )
    channel_inputs = _resolve_calculation_inputs(
        revision=snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        backend_casilla_inputs=backend_casilla_inputs,
        resolved_bindings=prepared.channels.bindings,
        casilla_inputs=prepared.casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        profile_text_casilla_inputs=resolve_profile_text_casilla_inputs(
            snapshot.revision,
            profile_fact_index(prepared.profile.record, prepared.profile.profile_decode_context.schema),
        ).values,
    )
    resolved_inputs = channel_inputs.casilla_inputs

    resolved_text_inputs = validated_text_input_casilla_ids(channel_inputs.text_casilla_inputs)
    _reject_clears_of_source_fed_casillas(
        cleared_casilla_ids,
        resolved_casilla_ids=(*resolved_inputs, *resolved_text_inputs),
    )
    # The row-field template outputs are dropped after the engine runs, so a
    # scalar input for one would be persisted with no observation to ground it.
    reject_row_field_template_scalar_inputs(snapshot.revision, (*resolved_inputs, *resolved_text_inputs))

    try:
        engine_result = _calculate_prepared_registry_snapshot(
            snapshot,
            resolved_inputs=resolved_inputs,
            resolved_text_inputs=resolved_text_inputs,
            period_date=prepared.period_date,
            binding_values=prepared.channels.bindings,
            enum_binding_values=prepared.channels.enum_bindings,
            relation_values=resolved_relations,
            unresolved_relation_ids=unresolved_relation_ids,
            unresolved_binding_ids=unresolved_binding_ids,
            date_binding_values=prepared.channels.date_bindings,
            boolean_binding_values=prepared.channels.boolean_bindings,
            closed_record_row_sets=closed_record_row_sets,
        )
    except RegistryValidationError as error:
        missing = ModeloWorkMissingInputError.from_registry_error(error)
        if missing is None:
            raise
        # This boundary precedes revision publication. Earlier migrations may
        # already have written state; later advisory failures never enter it.
        raise missing from error

    replay_payloads = _build_calculation_replay_payloads(
        resolved_inputs=resolved_inputs,
        resolved_bindings=prepared.channels.bindings,
        resolved_enum_bindings=prepared.channels.enum_bindings,
        resolved_date_bindings=prepared.channels.date_bindings,
        resolved_relations=resolved_relations,
        resolved_row_bindings=_optional_mapping_as_dict(row_binding_values),
        resolved_boolean_bindings=prepared.channels.boolean_bindings,
    )
    casilla_values = dict(engine_result.values)
    require_m303_regimen_simplificado_annual_summary_arrival_values(
        casilla_values=casilla_values,
        handoff=m303_regimen_simplificado_annual_summary_handoff,
    )
    _raise_if_m390_303_reconciliation_would_save_silent_zero(
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_values=casilla_values,
        resolved_binding_values=prepared.channels.bindings,
    )
    typed_observations = _build_typed_observations(engine_result=engine_result, snapshot=snapshot)
    casilla_values, typed_observations = _drop_row_field_template_outputs(
        revision=snapshot.revision,
        casilla_values=casilla_values,
        observations=typed_observations,
    )
    validated_filing_instance_evidence = validate_m303_filing_instance_evidence_for_revision(
        work_unit=work_unit,
        registry_snapshot=snapshot,
        evidence=filing_instance_evidence,
        casilla_values=casilla_values,
        observations=typed_observations,
        operation=ports.operation,
        profile=prepared.profile,
    )

    return (
        engine_result,
        replay_payloads,
        casilla_values,
        typed_observations,
        validated_filing_instance_evidence,
        resolved_text_inputs,
    )
