"""Public saved-reconciliation fixture shared by application and transport verification."""

from datetime import UTC, datetime
from uuid import UUID

from ..reconciliation_records import (
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationVerdict,
)

RECONCILIATION_PROFILE_FIXTURE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def reconciliation_history_entry_fixture(
    *,
    event_id: str,
    work_unit_id: str = "1" * 64,
    bucket_id: UUID = RECONCILIATION_PROFILE_FIXTURE,
    reconciled_at: datetime = datetime(2026, 3, 10, 12, tzinfo=UTC),
    source_path: str = "C:/synthetic/evidence/receipt.pdf",
    actor: str = "synthetic-test-operator",
) -> ModeloReconciliationHistoryEntry:
    return ModeloReconciliationHistoryEntry(
        event_id=event_id,
        bucket_id=str(bucket_id),
        work_unit_id=work_unit_id,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_path=source_path,
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diff_count=1,
        diffs=(
            ModeloReconciliationDiff(
                field_name="total_ingresar",
                work_unit_value="100.00",
                evidence_value="101.00",
                kind="total_ingresar_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        ),
        actor=actor,
        reconciled_at=reconciled_at,
    )
