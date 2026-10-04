"""Read persisted comparisons without re-parsing or re-grounding their evidence."""

from __future__ import annotations

from ...core.hashing import content_hash_hex
from ...core.period import Period
from ...domain.modelos.codes import ModeloCode
from ..modelo.reconciliation_records import ModeloReconciliationRecord
from .workspace import (
    AeatSyncDiscrepancyKind,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceReconciliationRowV1,
)


def reconciliation_rows(
    *,
    bucket_id: str,
    subject_key: str,
    records: tuple[ModeloReconciliationRecord, ...],
) -> tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceReconciliationRowV1], ...]:
    """Show the latest stored comparison for each work unit and evidence identity.

    These are historical verdicts at the displayed comparison instant, not a
    new comparison against whichever calculation revision happens to be current.
    """
    latest: dict[tuple[str, str, str], ModeloReconciliationRecord] = {}
    for record in records:
        if record.bucket_id != bucket_id:
            raise AeatSyncWorkspaceProjectionError("reconciliation belongs to another profile")
        # Older records can omit the source. Their evidence cannot be proven
        # identical, so retain each comparison rather than collapsing them.
        key = (str(record.work_unit_id), record.source_kind.value, record.source_ref or record.bucket_event_id)
        previous = latest.get(key)
        if previous is None or (record.reconciled_at, record.bucket_event_id) > (
            previous.reconciled_at,
            previous.bucket_event_id,
        ):
            latest[key] = record
    return tuple(
        AeatSyncWorkspaceFactV1(
            bucket_id=bucket_id,
            subject_key=subject_key,
            row=AeatSyncWorkspaceReconciliationRowV1(
                modelo=ModeloCode(record.registry_snapshot_ref.modelo),
                filing_year=record.registry_snapshot_ref.modelo_year,
                period=Period.from_year_and_code(
                    record.registry_snapshot_ref.modelo_year, record.registry_snapshot_ref.period
                ),
                local_state=AeatSyncSourceState.PRESENT,
                aeat_state=AeatSyncSourceState.CONFLICT
                if record.diffs
                else AeatSyncSourceState.INCOMPLETE
                if record.advisories
                else AeatSyncSourceState.PRESENT,
                local_observed_at=record.reconciled_at,
                aeat_observed_at=record.reconciled_at,
                discrepancy_kind=AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE
                if record.diffs
                else AeatSyncDiscrepancyKind.INCOMPLETE
                if record.advisories
                else AeatSyncDiscrepancyKind.NONE,
                local_value=record.diffs[0].work_unit_value if record.diffs else None,
                aeat_value=record.diffs[0].evidence_value if record.diffs else None,
                reconciliation_state=AeatSyncReconciliationState.UNRESOLVED
                if record.diffs or record.advisories
                else AeatSyncReconciliationState.NO_ACTION,
                evidence_kind=record.source_kind,
                diffs=record.diffs,
                advisory_count=len(record.advisories),
                comparison_id=record.bucket_event_id,
                work_unit_id=record.work_unit_id,
                evidence_id=content_hash_hex({"kind": record.source_kind.value, "source": key[2]}),
                historical=True,
            ),
        )
        for key, record in sorted(latest.items())
    )
