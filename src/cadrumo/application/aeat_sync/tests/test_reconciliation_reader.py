"""Stored comparison readback must not depend on a local filing record."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from ...modelo.reconciliation_records import ModeloReconciliationDiff, ModeloReconciliationDiffKind
from ..workspace import (
    AeatSyncDiscrepancyKind,
    AeatSyncOverviewArea,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceZone,
)
from .reconciliation_fixtures import reconciliation_projection, reconciliation_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BUCKET = "00000000-0000-4000-8000-000000000001"
_NOW = datetime(filing_year_envelope().horizon, 10, 4, tzinfo=UTC)


def test_saved_calculation_comparison_renders_without_local_filing_or_register_capture() -> None:
    record = reconciliation_record()
    projection = reconciliation_projection((record,))
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
    projection = reconciliation_projection(())
    assert projection.reconciliation == ()
    zone = next(zone for zone in projection.zones if zone.zone is AeatSyncWorkspaceZone.RECONCILIATION)
    assert zone.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert zone.item_count == 0
    assert reconciliation_projection((reconciliation_record(mismatches=False),)).reconciliation[0].advisory_count == 1


def test_mixed_profile_history_is_rejected() -> None:
    record = reconciliation_record().model_copy(update={"bucket_id": "00000000-0000-4000-8000-000000000002"})
    with pytest.raises(AeatSyncWorkspaceProjectionError):
        reconciliation_projection((record,))


def test_distinct_evidence_and_work_units_cannot_hide_existing_drift() -> None:
    declaration = reconciliation_record().model_copy(
        update={"source_kind": ModeloReconciliationEvidenceKind.DECLARATION, "source_ref": "file-a"}
    )
    receipt = reconciliation_record(mismatches=False).model_copy(
        update={"bucket_event_id": "c" * 64, "reconciled_at": _NOW + timedelta(seconds=1)}
    )
    other_work = declaration.model_copy(update={"work_unit_id": "d" * 64, "bucket_event_id": "e" * 64})
    other_file = declaration.model_copy(update={"source_ref": "file-b", "bucket_event_id": "f" * 64})
    projection = reconciliation_projection((declaration, receipt, other_work, other_file))
    assert len(projection.reconciliation) == 4
    assert sum(bool(row.diffs) for row in projection.reconciliation) == 3
    assert all(
        row.historical and row.comparison_id and row.work_unit_id and row.evidence_id
        for row in projection.reconciliation
    )
    overview = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.RECONCILIATION)
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE


def test_repeat_comparison_supersedes_only_same_work_and_evidence() -> None:
    earlier = reconciliation_record().model_copy(update={"calculation_revision_id": "a" * 64})
    later = earlier.model_copy(update={"bucket_event_id": "c" * 64, "reconciled_at": _NOW + timedelta(seconds=1)})
    (row,) = reconciliation_projection((later, earlier)).reconciliation
    assert row.comparison_id == later.bucket_event_id
    assert row.calculation_revision_id == earlier.calculation_revision_id


@pytest.mark.parametrize("revision", [None, "d" * 64])
def test_different_or_unknown_calculation_cannot_hide_prior_drift(revision: str | None) -> None:
    earlier = reconciliation_record().model_copy(
        update={"calculation_revision_id": "a" * 64 if (revision is not None and revision) else None}
    )
    later = earlier.model_copy(
        update={
            "calculation_revision_id": revision,
            "bucket_event_id": "c" * 64,
            "diffs": (),
            "reconciled_at": _NOW + timedelta(seconds=1),
        }
    )
    rows = reconciliation_projection((earlier, later)).reconciliation
    assert len(rows) == 2
    assert any(row.diffs for row in rows)


def test_history_without_source_identity_does_not_assume_the_same_evidence() -> None:
    first = reconciliation_record().model_copy(update={"source_ref": ""})
    second = first.model_copy(update={"bucket_event_id": "c" * 64})
    rows = reconciliation_projection((first, second)).reconciliation
    assert len(rows) == 2
    assert len({row.evidence_id for row in rows}) == 2


def test_advisory_only_comparison_is_incomplete_in_row_and_overview() -> None:
    projection = reconciliation_projection((reconciliation_record(mismatches=False),))
    (row,) = projection.reconciliation
    assert row.discrepancy_kind is AeatSyncDiscrepancyKind.INCOMPLETE
    overview = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.RECONCILIATION)
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.INCOMPLETE


@pytest.mark.parametrize("grounded", [False, True])
def test_populated_reconciliation_survives_complete_workbench_public_roundtrip(grounded: bool) -> None:
    from ...search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
    from ...workbench_generation import assemble_workbench_generation
    from ...workbench_generation_contracts import WorkbenchGenerationInputsV1, WorkbenchGenerationSourceResultV1
    from ...workbench_generation_projection import (
        WorkbenchGenerationOperationProjection,
        project_workbench_generation,
        restore_workbench_generation,
    )

    record = reconciliation_record()
    if grounded:
        record = record.model_copy(
            update={
                "source_kind": ModeloReconciliationEvidenceKind.DECLARATION,
                "diffs": tuple(
                    ModeloReconciliationDiff(
                        field_name=f"casilla-{index}",
                        work_unit_value="0.00",
                        evidence_value="123.45",
                        kind="casilla_value_mismatch",
                        diff_kind=ModeloReconciliationDiffKind.CASILLA,
                        legal_refs=("ley-37-1992:art-99",),
                        source_refs=("aeat-dr-303-2024-early",),
                    )
                    for index in range(14)
                ),
            }
        )
    records = (record, reconciliation_record()) if grounded else (record,)
    missing = WorkbenchGenerationSourceResultV1.never_captured(refusal="test.not_captured")
    generation = assemble_workbench_generation(
        WorkbenchGenerationInputsV1(
            assembled_at=_NOW,
            home=missing,
            ledger=missing,
            declarations=missing,
            declarations_calendar=missing,
            modelo=missing,
            aeat_sync=WorkbenchGenerationSourceResultV1.available(reconciliation_projection(records), observed_at=_NOW),
            ledger_admission=WorkbenchDestinationAdmission(
                destination="workbench.ledger",
                state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
                reason_code="test.not_captured",
            ),
            declarations_admission=WorkbenchDestinationAdmission(
                destination="workbench.declarations",
                state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
                reason_code="test.not_captured",
            ),
            aeat_sync_admission=WorkbenchDestinationAdmission(
                destination="workbench.aeat_sync", state=WorkbenchDestinationAdmissionState.AVAILABLE
            ),
        )
    )
    public = project_workbench_generation(UUID(_BUCKET), generation)
    restored = restore_workbench_generation(
        WorkbenchGenerationOperationProjection.model_validate_json(public.model_dump_json())
    )
    assert restored == generation
