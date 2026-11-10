"""Shared reconciliation records and canonical workspace projections for tests."""

from __future__ import annotations

from datetime import UTC, datetime

from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_serving_period
from ...modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from ...modelo.reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
)
from ..workspace_reader import read_local_aeat_sync_workspace_projection
from .test_workspace_reader import unrelated_contracts

_BUCKET = "00000000-0000-4000-8000-000000000001"
_YEAR = filing_year_envelope().horizon
_NOW = datetime(_YEAR, 10, 4, tzinfo=UTC)


def reconciliation_record(*, mismatches: bool = True) -> ModeloReconciliationRecord:
    """Build a stored comparison with explicit identity and advisory evidence."""
    return ModeloReconciliationRecord(
        bucket_event_id="a" * 64,
        bucket_id=_BUCKET,
        work_unit_id="b" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            modelo_year=_YEAR,
            period="1T",
            revision_id=str(revision_serving_period("303", _YEAR, "1T").id),
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
        subject_key="00001005Q",
        observed_at=_NOW,
        filings=(),
        operation_contracts=unrelated_contracts(),
        reconciliations=records,
    )
