"""Validate declaration, calculation, filing and lifecycle catalogue joins."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ...core.identity.bucket import BucketId
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
)
from ...domain.modelos.filing_record import (
    ModeloRecord,
    ModeloRecordStatus,
)
from ...domain.modelos.work_unit import WorkUnit
from .declarations_workspace_contracts import DeclarationsSanitizedLifecycleFactV1, DeclarationsWorkspaceProjectionError

if TYPE_CHECKING:
    pass


def validate_declarations_catalogue_joins(
    *,
    bucket_id: BucketId,
    units: tuple[WorkUnit, ...],
    revisions: tuple[CalculationRevision, ...],
    filings: tuple[ModeloRecord, ...],
    lifecycle_facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
) -> None:
    """Refuse any contradictory join before safe rows are projected.

    Parameter types: ``revisions`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`),
    ``filings`` (:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`).
    """
    unit_by_id = {unit.work_unit_id: unit for unit in units}
    revision_by_id = {revision.calculation_revision_id: revision for revision in revisions}
    filing_by_id = {record.filing_record_id: record for record in filings}
    _validate_work_catalogue(bucket_id, units)
    _validate_unique_lifecycle_facts(lifecycle_facts)
    _validate_revisions_have_declarations(revisions, unit_by_id)
    _validate_declaration_pointers(units, revision_by_id, filing_by_id)
    _validate_filing_records(bucket_id, filings, unit_by_id, revision_by_id, filing_by_id)
    _validate_revision_filing_records(revisions, filings)
    _validate_lifecycle_fact_declarations(lifecycle_facts, unit_by_id)


def _validate_work_catalogue(bucket_id: BucketId, units: tuple[WorkUnit, ...]) -> None:
    if any(unit.bucket_id != bucket_id for unit in units):
        raise DeclarationsWorkspaceProjectionError("work catalogue contains a foreign bucket")
    natural_addresses = tuple((unit.modelo, unit.filing_year, unit.period) for unit in units)
    if len(natural_addresses) != len(set(natural_addresses)):
        raise DeclarationsWorkspaceProjectionError("work catalogue contains duplicate declaration addresses")


def _validate_unique_lifecycle_facts(facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...]) -> None:
    if len({fact.fact_id for fact in facts}) != len(facts):
        raise DeclarationsWorkspaceProjectionError("lifecycle facts contain duplicate identities")


def _validate_revisions_have_declarations(
    revisions: tuple[CalculationRevision, ...],
    unit_by_id: Mapping[str, WorkUnit],
) -> None:
    for revision in revisions:
        if revision.work_unit_id not in unit_by_id:
            raise DeclarationsWorkspaceProjectionError("calculation revision has no declaration")


def _validate_declaration_pointers(
    units: tuple[WorkUnit, ...],
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    for unit in units:
        _validate_declaration_revision_pointers(unit, revision_by_id)
        _validate_declaration_filing_pointers(unit, revision_by_id, filing_by_id)


def _validate_declaration_revision_pointers(
    unit: WorkUnit,
    revision_by_id: Mapping[str, CalculationRevision],
) -> None:
    for revision_id in (unit.current_calculation_revision_id, unit.filed_calculation_revision_id):
        if revision_id is None:
            continue
        revision = revision_by_id.get(revision_id)
        if revision is None or revision.work_unit_id != unit.work_unit_id:
            raise DeclarationsWorkspaceProjectionError("declaration revision pointer is missing or contradictory")


def _validate_declaration_filing_pointers(
    unit: WorkUnit,
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    filed_revision_id = unit.filed_calculation_revision_id
    current_filing_id = unit.current_filing_record_id
    if (filed_revision_id is None) != (current_filing_id is None):
        raise DeclarationsWorkspaceProjectionError("declaration filing pointers must be present or absent together")
    if filed_revision_id is None or current_filing_id is None:
        return
    revision = revision_by_id.get(filed_revision_id)
    record = filing_by_id.get(current_filing_id)
    if not _is_current_filing_pointer(unit, revision, record):
        raise DeclarationsWorkspaceProjectionError("declaration filing pointers do not resolve to one current filing")


def _is_current_filing_pointer(
    unit: WorkUnit,
    revision: CalculationRevision | None,
    record: ModeloRecord | None,
) -> bool:
    return (
        revision is not None
        and record is not None
        and revision.work_unit_id == unit.work_unit_id
        and record.work_unit_id == unit.work_unit_id
        and record.calculation_revision_id == revision.calculation_revision_id
        and record.status is ModeloRecordStatus.VIGENTE
        and revision.state is CalculationRevisionState.PRESENTADO
    )


def _validate_filing_records(
    bucket_id: BucketId,
    filings: tuple[ModeloRecord, ...],
    unit_by_id: Mapping[str, WorkUnit],
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    for record in filings:
        _validate_filing_record(bucket_id, record, unit_by_id, revision_by_id, filing_by_id)


def _validate_filing_record(
    bucket_id: BucketId,
    record: ModeloRecord,
    unit_by_id: Mapping[str, WorkUnit],
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    unit = unit_by_id.get(record.work_unit_id)
    revision = revision_by_id.get(record.calculation_revision_id)
    if record.bucket_id != bucket_id or unit is None or revision is None:
        raise DeclarationsWorkspaceProjectionError("filing record has no same-bucket declaration and revision")
    if revision.work_unit_id != unit.work_unit_id:
        raise DeclarationsWorkspaceProjectionError("filing revision belongs to another declaration")
    if (record.modelo, record.filing_year, record.period) != (unit.modelo, unit.filing_year, unit.period):
        raise DeclarationsWorkspaceProjectionError("filing address contradicts its declaration")
    if record.status is ModeloRecordStatus.VIGENTE and not _record_is_current(unit, revision, record):
        raise DeclarationsWorkspaceProjectionError("current filing pointers or revision state contradict")
    if record.status is ModeloRecordStatus.SUPERSEDIDO and not _record_has_valid_successor(
        record, revision, filing_by_id
    ):
        raise DeclarationsWorkspaceProjectionError("superseded filing successor is missing or contradictory")


def _record_is_current(unit: WorkUnit, revision: CalculationRevision, record: ModeloRecord) -> bool:
    return (
        unit.current_filing_record_id == record.filing_record_id
        and unit.filed_calculation_revision_id == record.calculation_revision_id
        and revision.state is CalculationRevisionState.PRESENTADO
    )


def _record_has_valid_successor(
    record: ModeloRecord,
    revision: CalculationRevision,
    filing_by_id: Mapping[str, ModeloRecord],
) -> bool:
    successor = filing_by_id.get(record.superseded_by_filing_record_id or "")
    return (
        revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
        and successor is not None
        and successor.work_unit_id == record.work_unit_id
        and (
            successor.modelo,
            successor.filing_year,
            successor.period,
            successor.member_nif,
        )
        == (record.modelo, record.filing_year, record.period, record.member_nif)
    )


def _validate_revision_filing_records(
    revisions: tuple[CalculationRevision, ...],
    filings: tuple[ModeloRecord, ...],
) -> None:
    records_by_revision: dict[str, list[ModeloRecord]] = {}
    for record in filings:
        records_by_revision.setdefault(record.calculation_revision_id, []).append(record)
    for revision in revisions:
        _validate_revision_filing_record(revision, records_by_revision)


def _validate_revision_filing_record(
    revision: CalculationRevision,
    records_by_revision: Mapping[str, list[ModeloRecord]],
) -> None:
    matching_records = records_by_revision.get(revision.calculation_revision_id, [])
    if revision.state is CalculationRevisionState.PRESENTADO and not _has_record_status(
        matching_records, ModeloRecordStatus.VIGENTE
    ):
        raise DeclarationsWorkspaceProjectionError("current filed revision has no current filing record")
    if revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO and not _has_record_status(
        matching_records, ModeloRecordStatus.SUPERSEDIDO
    ):
        raise DeclarationsWorkspaceProjectionError("superseded revision has no superseded filing record")


def _has_record_status(records: list[ModeloRecord], status: ModeloRecordStatus) -> bool:
    return any(record.status is status for record in records)


def _validate_lifecycle_fact_declarations(
    facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
    unit_by_id: Mapping[str, WorkUnit],
) -> None:
    if any(fact.work_unit_id not in unit_by_id for fact in facts):
        raise DeclarationsWorkspaceProjectionError("lifecycle fact has no declaration")
