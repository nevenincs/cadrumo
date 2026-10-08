"""Shared reconciliation records and canonical workspace projections for tests."""

from __future__ import annotations

from datetime import UTC, datetime

from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...modelo.reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
)
from ..workspace_reader import read_local_aeat_sync_workspace_projection
from .test_workspace_reader import _unrelated_contracts

_BUCKET = "00000000-0000-4000-8000-000000000001"
_NOW = datetime(2026, 10, 4, tzinfo=UTC)


def reconciliation_record(*, mismatches: bool = True) -> ModeloReconciliationRecord:
    """Build a stored comparison with explicit identity and advisory evidence."""
    return ModeloReconciliationRecord(
        bucket_event_id="a" * 64,
        bucket_id=_BUCKET,
        work_unit_id="b" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303", modelo_year=2024, period="1T", revision_id="2024-hasta-08-y-2t"
        ),
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref="test-evidence",
        verdict=ModeloReconciliationVerdict.MISMATCHES if mismatches else ModeloReconciliationVerdict.MATCHES,
        diffs=(
            ModeloReconciliationDiff(
                field_name="total", work_unit_value="0.00", evidence_value="125.50", kind="total_mismatch"
            ),
        )
        if mismatches
        else (),
        advisories=(ModeloReconciliationAdvisory(code="identity_anchor_unverified", message="Unverified identity"),),
        actor="test",
        reconciled_at=_NOW,
    )


def reconciliation_projection(records):
    """Project stored comparisons without requiring a separate local filing."""
    return read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key="00000001R",
        observed_at=_NOW,
        filings=(),
        operation_contracts=_unrelated_contracts(),
        reconciliations=records,
    )
