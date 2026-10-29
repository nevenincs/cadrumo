"""Draft calculation revision persistence.

Core types:
:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.hashing import sha256_hex
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.secure_object_write import SecureObjectWrite
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.record_row_membership import ClosedRecordRowSet
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.calculations.row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ...domain.calculations.row_source_identity import RowBindingKey, RowSourceIdentity
from ...domain.modelos.calculation_repository import upsert_calculation_revision
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303RegimenSimplificadoAnnualSummaryHandoff,
)
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from ...domain.modelos.calculation_revision_sources import CalculationSourceIssue, CalculationSourceRef
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
)
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .calculation_publication import CalculationRevisionPublication
from .filing_revision_persistence import validate_filing_instance_evidence_for_work_unit
from .modelo_bucket_events import build_modelo_bucket_event


def _source_provenance_trace_sha256(source_provenance: tuple[CalculationSourceRef, ...]) -> str:
    """Deterministic digest of the persisted source-mesh provenance trace.

    Emitted on the ``modelo.calculation.created`` bucket event so an audit reader
    can detect a source-connectivity change without decrypting the calculation
    revision. The digest folds each provenance row's stable
    complete resolver, ownership, lineage, reference, and fingerprint identity in a sort-canonical
    order so the value is order-independent, mirroring the existing
    ``borrador_bindings_trace_sha256`` join-record pattern. An empty provenance
    tuple yields the digest of the empty string.
    """
    lines = sorted(
        f"{ref.resolver_id}\x1f{ref.resolved_binding_source.value}\x1f"
        f"{ref.contributor_source_kind}\x1f"
        f"{ref.contributor_binding_source.value if ref.contributor_binding_source is not None else ''}\x1f"
        f"{ref.lineage_role.value}\x1f{ref.source_ref}\x1f{ref.parent_source_ref or ''}\x1f"
        f"{ref.fingerprint or ''}"
        for ref in source_provenance
    )
    return sha256_hex("\n".join(lines).encode("utf-8"))


def _validate_calculation_revision_target(
    *,
    work_unit: WorkUnit,
    registry_snapshot_ref: RegistrySnapshotRef,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    filing_instance_evidence: FilingInstanceEvidence | None,
) -> None:
    """Validate the work-unit coordinates before deriving or persisting a revision."""
    validate_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        evidence=filing_instance_evidence,
        operation="calculation revision creation",
    )
    expected_snapshot_ref = RegistrySnapshotRef(
        modelo=work_unit.modelo,
        revision_id=work_unit.revision_id,
        modelo_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    if registry_snapshot_ref != expected_snapshot_ref:
        raise ValueError("calculation revision registry snapshot ref must equal the parent work-unit coordinate")
    if any(item.materialization_rule_version != work_unit.revision_id for item in row_casilla_provenance.values()):
        raise ValueError("row casilla materialization rule version must equal the parent work-unit revision")


def _stamp_annual_summary_handoff(
    handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
    revision_id: str,
) -> M303RegimenSimplificadoAnnualSummaryHandoff | None:
    """Bind an annual-summary handoff to the revision content address."""
    if handoff is None:
        return None
    return handoff.stamped_for_target_calculation_revision(revision_id)


def _build_calculation_revision(
    *,
    revision_id: str,
    work_unit_id: str,
    registry_snapshot_ref: RegistrySnapshotRef,
    input_values_by_casilla_id: dict[CasillaId, str],
    binding_overrides: dict[BindingId, str],
    row_binding_values: dict[BindingId, dict[str, str]],
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...],
    row_casilla_values: Mapping[RowCasillaKey, Decimal],
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    relation_overrides: dict[RelationId, str],
    source_transaction_ids: tuple[str, ...],
    m210_official_tipo_renta_code: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    cleared_casilla_ids: tuple[CasillaId, ...],
    operator_layer: CalculationOperatorLayer | None,
    rendering_snapshot: CalculationRenderingSnapshot | None,
    casilla_values: dict[CasillaId, Decimal],
    observations: tuple[CasillaObservation, ...],
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...],
    source_provenance: tuple[CalculationSourceRef, ...],
    source_issues: tuple[CalculationSourceIssue, ...],
    detail_rows: tuple[ModeloDetailRow, ...],
    ledger_filing_snapshot: LedgerFilingSnapshot | None,
    filing_instance_evidence: FilingInstanceEvidence | None,
    m303_regimen_simplificado_annual_summary_handoff: (M303RegimenSimplificadoAnnualSummaryHandoff | None),
    now: datetime,
) -> CalculationRevision:
    """Materialize a draft revision from the already-derived calculation inputs."""
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_overrides=relation_overrides,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        rendering_snapshot=rendering_snapshot,
        casilla_values=casilla_values,
        observations=observations,
        unresolved_outcomes=unresolved_outcomes,
        source_provenance=source_provenance,
        source_issues=source_issues,
        detail_rows=detail_rows,
        ledger_filing_snapshot=ledger_filing_snapshot,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        created_at=now,
        updated_at=now,
    )


def _duplicate_calculation_work_units(
    *,
    existing: CalculationRevision,
    revision_id: str,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    now: datetime,
) -> WorkUnitCatalogue:
    """Restore a duplicate draft as current without touching sealed revisions."""
    if existing.state is not CalculationRevisionState.BORRADOR:
        return work_units
    if work_unit.current_calculation_revision_id == revision_id:
        return work_units
    return upsert_work_unit(
        work_units,
        work_unit.model_copy(
            update={
                "current_calculation_revision_id": revision_id,
                "updated_at": now,
            },
        ),
    )


def _duplicate_calculation_secure_writes(
    *,
    revision_id: str,
    additional_secure_object_writes_for_revision: (Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None),
) -> tuple[SecureObjectWrite, ...]:
    """Build duplicate-path side-effect writes with no fresh event id."""
    if additional_secure_object_writes_for_revision is None:
        return ()
    return additional_secure_object_writes_for_revision(revision_id, None)


def _persist_duplicate_calculation_revision(
    *,
    existing: CalculationRevision,
    revision_id: str,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    work_units_revision_id: str,
    now: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    additional_secure_object_writes_for_revision: (Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None),
) -> CalculationRevisionPublication:
    """Guard and co-commit duplicate-result pointer and side-effect writes."""
    duplicate_work_units = _duplicate_calculation_work_units(
        existing=existing,
        revision_id=revision_id,
        work_unit=work_unit,
        work_units=work_units,
        now=now,
    )
    duplicate_writes = _duplicate_calculation_secure_writes(
        revision_id=revision_id,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )
    if duplicate_work_units is work_units and not duplicate_writes:
        return CalculationRevisionPublication(revision=existing, work_unit=work_unit, published=False)
    # Guarded, never a bare `.save`: an unguarded write here would silently
    # discard a concurrent catalogue change this branch never observed, and it
    # is the one place a co-committed receipt write could otherwise be dropped.
    work_unit_repository.save_with_secure_object_writes(
        duplicate_work_units,
        duplicate_writes,
        expected_revision_id=work_units_revision_id,
    )
    return CalculationRevisionPublication(
        revision=existing,
        work_unit=duplicate_work_units.work_units[work_unit.work_unit_id],
        published=True,
    )


def _advance_calculation_work_unit(
    *,
    work_units: WorkUnitCatalogue,
    work_unit: WorkUnit,
    revision_id: str,
    now: datetime,
) -> WorkUnitCatalogue:
    """Advance the parent pointer for a newly persisted draft revision."""
    return upsert_work_unit(
        work_units,
        work_unit.model_copy(
            update={
                "current_calculation_revision_id": revision_id,
                "updated_at": now,
            },
        ),
    )


def _build_calculation_created_event(
    *,
    revision_id: str,
    work_unit_id: str,
    work_unit: WorkUnit,
    input_values_by_casilla_id: dict[CasillaId, str],
    row_binding_values: dict[BindingId, dict[str, str]],
    row_casilla_values: Mapping[RowCasillaKey, Decimal],
    casilla_values: dict[CasillaId, Decimal],
    formula_count: int,
    source_transaction_ids: tuple[str, ...],
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    observations: tuple[CasillaObservation, ...],
    source_provenance: tuple[CalculationSourceRef, ...],
    actor: str,
    now: datetime,
) -> BucketEvent:
    """Build the compact audit event for a newly created calculation."""
    return build_modelo_bucket_event(
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=revision_id,
        payload={
            "calculation_revision_id": revision_id,
            "work_unit_id": work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "input_casilla_count": str(len(input_values_by_casilla_id)),
            "row_binding_count": str(sum(len(rows) for rows in row_binding_values.values())),
            "row_casilla_count": str(len(row_casilla_values)),
            "casilla_count": str(len(casilla_values)),
            "formula_count": str(formula_count),
            "source_transaction_count": str(len(source_transaction_ids)),
            "borrador_snapshot_id": borrador_snapshot_id or "",
            "borrador_participated": "true" if bindings_sourced_from_borrador else "false",
            "borrador_binding_count": str(len(bindings_sourced_from_borrador)),
            "borrador_bindings_trace_sha256": sha256_hex(
                "\n".join(bindings_sourced_from_borrador).encode("utf-8"),
            ),
            "has_provenance": "true" if observations else "false",
            "source_provenance_count": str(len(source_provenance)),
            "source_provenance_trace_sha256": _source_provenance_trace_sha256(source_provenance),
        },
    )


def _additional_calculation_secure_writes(
    *,
    revision_id: str,
    bucket_event_id: str,
    additional_secure_object_writes_for_revision: (Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None),
) -> tuple[SecureObjectWrite, ...]:
    """Build new-revision side-effect writes after the event id exists."""
    if additional_secure_object_writes_for_revision is None:
        return ()
    return additional_secure_object_writes_for_revision(revision_id, bucket_event_id)


def _persist_new_calculation_revision(
    *,
    revision: CalculationRevision,
    revisions: CalculationRevisionCatalogue,
    revisions_revision_id: str,
    advanced_work_units: WorkUnitCatalogue,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    work_units_revision_id: str,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    created_event: BucketEvent,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    additional_secure_object_writes_for_revision: (Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None),
) -> None:
    """Atomically persist the draft, current pointer, event, and side effects."""
    calculation_repository.save_with_secure_object_writes(
        upsert_calculation_revision(revisions, revision),
        (
            work_unit_repository.to_secure_object_write(
                advanced_work_units,
                expected_revision_id=work_units_revision_id,
            ),
            bucket_event_history_write(bucket_event_repository, (created_event,)),
            *_additional_calculation_secure_writes(
                revision_id=revision.calculation_revision_id,
                bucket_event_id=created_event.event_id,
                additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
            ),
        ),
        expected_revision_id=revisions_revision_id,
    )


def _validate_calculation_publication_scope(
    *,
    operation: PinnedAuthorityOperation,
    work_unit: WorkUnit,
    work_unit_id: str,
    registry_snapshot_ref: RegistrySnapshotRef,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    filing_instance_evidence: FilingInstanceEvidence | None,
    rendering_snapshot: CalculationRenderingSnapshot | None,
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...],
) -> None:
    _validate_calculation_revision_target(
        work_unit=work_unit,
        registry_snapshot_ref=registry_snapshot_ref,
        row_casilla_provenance=row_casilla_provenance,
        filing_instance_evidence=filing_instance_evidence,
    )
    if rendering_snapshot is not None and (
        rendering_snapshot.authority_generation != operation.pin().logical_generation
        or rendering_snapshot.registry_snapshot.snapshot_ref != registry_snapshot_ref
    ):
        raise ModeloValidationError("rendering snapshot does not belong to the admitted calculation scope")
    if any(
        row_set.bucket_id != work_unit.bucket_id
        or row_set.work_unit_id != work_unit_id
        or row_set.registry_snapshot_ref != registry_snapshot_ref
        or row_set.authority_generation != operation.pin().logical_generation
        for row_set in closed_record_row_sets
    ):
        raise ModeloValidationError("closed record rows do not belong to the admitted calculation scope")


def _publish_new_calculation_revision(
    *,
    revision: CalculationRevision,
    revisions: CalculationRevisionCatalogue,
    revisions_revision_id: str,
    revision_id: str,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    work_unit_id: str,
    input_values_by_casilla_id: dict[CasillaId, str],
    row_binding_values: dict[BindingId, dict[str, str]],
    row_casilla_values: Mapping[RowCasillaKey, Decimal],
    casilla_values: dict[CasillaId, Decimal],
    formula_count: int,
    source_transaction_ids: tuple[str, ...],
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    observations: tuple[CasillaObservation, ...],
    source_provenance: tuple[CalculationSourceRef, ...],
    actor: str,
    now: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    work_units_revision_id: str,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    additional_secure_object_writes_for_revision: Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None,
) -> CalculationRevisionPublication:
    """Co-commit a new draft, its work-unit pointer and the audit event."""
    advanced_work_units = _advance_calculation_work_unit(
        work_units=work_units,
        work_unit=work_unit,
        revision_id=revision_id,
        now=now,
    )
    created_event = _build_calculation_created_event(
        revision_id=revision_id,
        work_unit_id=work_unit_id,
        work_unit=work_unit,
        input_values_by_casilla_id=input_values_by_casilla_id,
        row_binding_values=row_binding_values,
        row_casilla_values=row_casilla_values,
        casilla_values=casilla_values,
        formula_count=formula_count,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        observations=observations,
        source_provenance=source_provenance,
        actor=actor,
        now=now,
    )
    # Commit the draft, pointer and history event together.
    _persist_new_calculation_revision(
        revision=revision,
        revisions=revisions,
        revisions_revision_id=revisions_revision_id,
        advanced_work_units=advanced_work_units,
        work_unit_repository=work_unit_repository,
        work_units_revision_id=work_units_revision_id,
        bucket_event_repository=bucket_event_repository,
        created_event=created_event,
        calculation_repository=calculation_repository,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )
    return CalculationRevisionPublication(
        revision=revision,
        work_unit=advanced_work_units.work_units[work_unit.work_unit_id],
        published=True,
    )


def _derive_revision_identity_and_handoff(
    *,
    work_unit_id: str,
    input_values_by_casilla_id: dict[CasillaId, str],
    binding_overrides: dict[BindingId, str],
    row_binding_values: dict[BindingId, dict[str, str]],
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...],
    row_casilla_values: Mapping[RowCasillaKey, Decimal],
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    relation_overrides: dict[RelationId, str],
    casilla_values: dict[CasillaId, Decimal],
    source_transaction_ids: tuple[str, ...],
    m210_official_tipo_renta_code: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    detail_rows: tuple[ModeloDetailRow, ...],
    source_issues: tuple[CalculationSourceIssue, ...],
    source_provenance: tuple[CalculationSourceRef, ...],
    filing_instance_evidence: FilingInstanceEvidence | None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
    cleared_casilla_ids: tuple[CasillaId, ...],
    operator_layer: CalculationOperatorLayer | None,
    rendering_snapshot: CalculationRenderingSnapshot | None,
) -> tuple[str, M303RegimenSimplificadoAnnualSummaryHandoff | None]:
    """Derive the content identity before stamping its annual handoff."""
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_overrides=relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        detail_rows=detail_rows,
        source_issues=source_issues,
        source_provenance=source_provenance,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        rendering_snapshot=rendering_snapshot,
    )
    stamped_annual_summary_handoff = _stamp_annual_summary_handoff(
        m303_regimen_simplificado_annual_summary_handoff,
        revision_id,
    )
    return revision_id, stamped_annual_summary_handoff


def persist_calculation_revision(
    *,
    operation: PinnedAuthorityOperation,
    work_unit_id: str,
    registry_snapshot_ref: RegistrySnapshotRef,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    work_units_revision_id: str,
    input_values_by_casilla_id: dict[CasillaId, str],
    binding_overrides: dict[BindingId, str],
    row_binding_values: dict[BindingId, dict[str, str]],
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
    row_casilla_values: Mapping[RowCasillaKey, Decimal],
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    relation_overrides: dict[RelationId, str],
    casilla_values: dict[CasillaId, Decimal],
    source_transaction_ids: tuple[str, ...],
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    observations: tuple[CasillaObservation, ...],
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    operator_layer: CalculationOperatorLayer | None = None,
    rendering_snapshot: CalculationRenderingSnapshot | None = None,
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...] = (),
    source_provenance: tuple[CalculationSourceRef, ...],
    source_issues: tuple[CalculationSourceIssue, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    detail_rows: tuple[ModeloDetailRow, ...],
    formula_count: int,
    actor: str,
    now: datetime,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    additional_secure_object_writes_for_revision: (
        Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None
    ) = None,
) -> CalculationRevisionPublication:
    """Persist a draft revision and return its publication and parent receipt.

    Takes ``observations`` as :class:`CasillaObservation` records.
    """
    _validate_calculation_publication_scope(
        operation=operation,
        work_unit=work_unit,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        row_casilla_provenance=row_casilla_provenance,
        filing_instance_evidence=filing_instance_evidence,
        rendering_snapshot=rendering_snapshot,
        closed_record_row_sets=closed_record_row_sets,
    )
    revision_id, stamped_annual_summary_handoff = _derive_revision_identity_and_handoff(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_overrides=relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        detail_rows=detail_rows,
        source_issues=source_issues,
        source_provenance=source_provenance,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        rendering_snapshot=rendering_snapshot,
    )
    # Guard the catalogue against concurrent calculations.
    revisions, revisions_revision_id = calculation_repository.load_revisioned(operation=operation)
    existing = revisions.get(revision_id)
    if existing is not None:
        return _persist_duplicate_calculation_revision(
            existing=existing,
            revision_id=revision_id,
            work_unit=work_unit,
            work_units=work_units,
            work_units_revision_id=work_units_revision_id,
            now=now,
            work_unit_repository=work_unit_repository,
            additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
        )
    revision = _build_calculation_revision(
        revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_overrides=relation_overrides,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        rendering_snapshot=rendering_snapshot,
        casilla_values=casilla_values,
        observations=observations,
        unresolved_outcomes=unresolved_outcomes,
        source_provenance=source_provenance,
        source_issues=source_issues,
        detail_rows=detail_rows,
        ledger_filing_snapshot=ledger_filing_snapshot,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=stamped_annual_summary_handoff,
        now=now,
    )
    return _publish_new_calculation_revision(
        revision=revision,
        revisions=revisions,
        revisions_revision_id=revisions_revision_id,
        revision_id=revision_id,
        work_unit=work_unit,
        work_units=work_units,
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        row_binding_values=row_binding_values,
        row_casilla_values=row_casilla_values,
        casilla_values=casilla_values,
        formula_count=formula_count,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        observations=observations,
        source_provenance=source_provenance,
        actor=actor,
        now=now,
        work_unit_repository=work_unit_repository,
        work_units_revision_id=work_units_revision_id,
        bucket_event_repository=bucket_event_repository,
        calculation_repository=calculation_repository,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )
