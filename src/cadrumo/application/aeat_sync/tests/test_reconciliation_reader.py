"""Stored comparison readback must not depend on a local filing record."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...modelo.reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
)
from ..workspace import (
    AeatSyncDiscrepancyKind,
    AeatSyncOverviewArea,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceZone,
)
from ..workspace_reader import read_local_aeat_sync_workspace_projection
from .test_workspace_reader import _unrelated_contracts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BUCKET = "00000000-0000-4000-8000-000000000001"
_NOW = datetime(2026, 10, 4, tzinfo=UTC)


def _record(*, mismatches: bool = True) -> ModeloReconciliationRecord:
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


def _projection(records):
    return read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key="00000001R",
        observed_at=_NOW,
        filings=(),
        operation_contracts=_unrelated_contracts(),
        reconciliations=records,
    )


def test_saved_calculation_comparison_renders_without_local_filing_or_register_capture() -> None:
    record = _record()
    projection = _projection((record,))
    (row,) = projection.reconciliation
    assert row.diffs == record.diffs
    assert row.local_value == "0.00" and row.aeat_value == "125.50"
    assert row.advisory_count == 1
    assert row.evidence_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE
    zone = next(zone for zone in projection.zones if zone.zone is AeatSyncWorkspaceZone.RECONCILIATION)
    assert zone.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert zone.item_count == 1
    overview = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.RECONCILIATION)
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE


def test_empty_history_is_available_but_not_a_matching_comparison() -> None:
    projection = _projection(())
    assert projection.reconciliation == ()
    zone = next(zone for zone in projection.zones if zone.zone is AeatSyncWorkspaceZone.RECONCILIATION)
    assert zone.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert zone.item_count == 0
    assert _projection((_record(mismatches=False),)).reconciliation[0].advisory_count == 1


def test_mixed_profile_history_is_rejected() -> None:
    record = _record().model_copy(update={"bucket_id": "00000000-0000-4000-8000-000000000002"})
    with pytest.raises(AeatSyncWorkspaceProjectionError):
        _projection((record,))


def test_distinct_evidence_and_work_units_cannot_hide_existing_drift() -> None:
    declaration = _record().model_copy(
        update={"source_kind": ModeloReconciliationEvidenceKind.DECLARATION, "source_ref": "file-a"}
    )
    receipt = _record(mismatches=False).model_copy(
        update={"bucket_event_id": "c" * 64, "reconciled_at": _NOW + timedelta(seconds=1)}
    )
    other_work = declaration.model_copy(update={"work_unit_id": "d" * 64, "bucket_event_id": "e" * 64})
    other_file = declaration.model_copy(update={"source_ref": "file-b", "bucket_event_id": "f" * 64})
    projection = _projection((declaration, receipt, other_work, other_file))
    assert len(projection.reconciliation) == 4
    assert sum(bool(row.diffs) for row in projection.reconciliation) == 3
    assert all(
        row.historical and row.comparison_id and row.work_unit_id and row.evidence_id
        for row in projection.reconciliation
    )
    overview = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.RECONCILIATION)
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE


def test_repeat_comparison_supersedes_only_same_work_and_evidence() -> None:
    earlier = _record()
    later = earlier.model_copy(update={"bucket_event_id": "c" * 64, "reconciled_at": _NOW + timedelta(seconds=1)})
    (row,) = _projection((later, earlier)).reconciliation
    assert row.comparison_id == later.bucket_event_id


def test_history_without_source_identity_does_not_assume_the_same_evidence() -> None:
    first = _record().model_copy(update={"source_ref": ""})
    second = first.model_copy(update={"bucket_event_id": "c" * 64})
    rows = _projection((first, second)).reconciliation
    assert len(rows) == 2
    assert len({row.evidence_id for row in rows}) == 2


def test_advisory_only_comparison_is_incomplete_in_row_and_overview() -> None:
    projection = _projection((_record(mismatches=False),))
    (row,) = projection.reconciliation
    assert row.discrepancy_kind is AeatSyncDiscrepancyKind.INCOMPLETE
    overview = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.RECONCILIATION)
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.INCOMPLETE


def test_populated_reconciliation_survives_complete_workbench_public_roundtrip() -> None:
    from ...tests.test_workbench_generation import _inputs
    from ...workbench_generation import assemble_workbench_generation
    from ...workbench_generation_contracts import WorkbenchGenerationSourceResultV1
    from ...workbench_generation_projection import (
        WorkbenchGenerationOperationProjection,
        project_workbench_generation,
        restore_workbench_generation,
    )

    generation = assemble_workbench_generation(
        _inputs(aeat_sync=WorkbenchGenerationSourceResultV1.available(_projection((_record(),)), observed_at=_NOW))
    )
    public = project_workbench_generation(UUID(_BUCKET), generation)
    restored = restore_workbench_generation(
        WorkbenchGenerationOperationProjection.model_validate_json(public.model_dump_json())
    )
    assert restored == generation
