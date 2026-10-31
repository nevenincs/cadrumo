"""New publications, literal text, retained failures and preservation of external notes."""

from asyncio import CancelledError
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from .....application.export.managed_artifact_ports import (
    ArtifactCreationReceipt,
    ManagedArtifactKind,
    ManagedArtifactPurpose,
)
from .....application.export.publication_receipt import PublicationFailure, PublicationReceipt, PublicationState
from .....application.export.review_snapshot import ReviewSnapshotContent, seal_review_snapshot
from .....application.storage.calc_sheets.records import SheetExportPlan, SheetReviewMetadata
from .....application.storage.calc_sheets.review_workbook import build_review_workbook
from .....application.storage.calc_sheets.tests.review_fixture import review_label, review_snapshot
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError, OutboundStorageNetworkError
from ..artifact_admission import GoogleArtifactAdmission
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from ..calc_sheets_apply import publish_review_plan
from ..managed_artifacts import ManagedGoogleArtifacts
from ..root_folder import ensure_root_folder
from .drive_files_server import DriveFilesEndpoint, drive_files_endpoint
from .review_sheets_server import ReviewSheetsEndpoint, review_sheets_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


@dataclass
class _PublicationWorld:
    receipts: GoogleArtifactReceiptStore
    root: ArtifactCreationReceipt
    artifacts: ManagedGoogleArtifacts
    publication: PublicationReceipt
    plan: SheetExportPlan[SheetReviewMetadata]
    drive: DriveFilesEndpoint
    sheets: ReviewSheetsEndpoint

    def publish(self) -> PublicationReceipt:
        return publish_review_plan(
            self.plan, publication=self.publication, artifacts=self.artifacts, sheets=self.sheets.service
        )


@contextmanager
def _publication_world(tmp_path: Path, failure_case: str) -> Iterator[_PublicationWorld]:
    """Open a real profile with Drive and Sheets endpoints and one injected failure (or none) armed."""
    snapshot = review_snapshot(amount="99.75")
    profile_id = uuid4()
    snapshot = seal_review_snapshot(
        ReviewSnapshotContent.model_validate(
            {
                **snapshot.model_dump(exclude={"snapshot_digest"}),
                "selection": {**snapshot.selection.model_dump(), "profile_id": profile_id},
            }
        )
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(profile_id)) as profile,
        drive_files_endpoint() as drive,
        review_sheets_endpoint() as sheets,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=profile_id)
        root_id = ensure_root_folder(drive.service, profile=str(profile_id), receipts=receipts)
        root = receipts.load(root_id)
        assert root is not None
        artifacts = ManagedGoogleArtifacts(
            GoogleArtifactAdmission(drive.service, profile_id=profile_id, root=root, receipts=receipts),
            receipts=receipts,
        )

        def handoff(action: str, *, writes: bool = False) -> None:
            if failure_case == "cancelled" and action == "sheets.spreadsheets.values.batchUpdate":
                raise CancelledError

        artifacts.admission.before_handoff = handoff
        publication = PublicationReceipt(
            publication_id=uuid4(), profile_id=profile_id, root=root, snapshot_digest=snapshot.snapshot_digest
        )
        plan = build_review_workbook(
            snapshot,
            publication_id=publication.publication_id,
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )
        sheets.fail_values = failure_case == "population"
        sheets.corrupt_baseline = failure_case == "baseline"
        if failure_case == "creation":
            drive.create_statuses.append(503)
        if failure_case == "movement":

            def move_created_sheet() -> None:
                drive.entries[-1]["parents"] = ["outside-managed-root"]

            sheets.after_values = move_created_sheet
        yield _PublicationWorld(
            receipts=receipts,
            root=root,
            artifacts=artifacts,
            publication=publication,
            plan=plan,
            drive=drive,
            sheets=sheets,
        )


_RAISED_BY_FAILURE_CASE = {
    "population": OutboundStorageNetworkError,
    "baseline": OutboundStorageConflictError,
    "movement": OutboundStorageConflictError,
    "cancelled": CancelledError,
    "creation": OutboundStorageNetworkError,
}
_RETAINED_FAILURE_BY_CASE = {
    "population": PublicationFailure.POPULATION,
    "baseline": PublicationFailure.INTEGRITY,
    "movement": PublicationFailure.POPULATION,
    "cancelled": PublicationFailure.CANCELLED,
    "creation": PublicationFailure.CREATE_UNKNOWN,
}


def _assert_creation_failure_reconciles_without_repopulating(
    world: _PublicationWorld, retained: PublicationReceipt
) -> None:
    parent = world.artifacts.admit(world.root, purpose=ManagedArtifactPurpose.RECONCILIATION)
    recovered = world.artifacts.reconcile_creation(
        parent,
        name=world.plan.metadata.document_title,
        kind=ManagedArtifactKind.REVIEW_SHEET,
        publication_id=world.publication.publication_id,
    )
    assert recovered.artifact_id == world.drive.entries[-1]["id"]
    assert world.receipts.load_publication(world.publication.publication_id) == retained
    assert world.sheets.calls == []
    with pytest.raises(OutboundStorageConflictError):
        world.publish()
    assert len(world.drive.created_bodies) == 2
    assert world.sheets.calls == []


@pytest.mark.parametrize("failure_case", ["population", "baseline", "movement", "cancelled", "creation"])
def test_a_failed_publication_is_retained_and_a_retry_never_repopulates_it(tmp_path: Path, failure_case: str) -> None:
    with _publication_world(tmp_path, failure_case) as world:
        with pytest.raises(_RAISED_BY_FAILURE_CASE[failure_case]):
            world.publish()
        retained = world.receipts.load_publication(world.publication.publication_id)
        assert retained is not None
        assert retained.state is (
            PublicationState.UNCERTAIN if failure_case == "creation" else PublicationState.PARTIAL
        )
        assert len(retained.artifacts) == (0 if failure_case == "creation" else 1)
        assert retained.failure is _RETAINED_FAILURE_BY_CASE[failure_case]
        if failure_case in {"movement", "cancelled"}:
            assert world.sheets.read_ranges == []
        world.sheets.calls.clear()
        with pytest.raises(OutboundStorageConflictError):
            world.publish()
        assert world.sheets.calls == []
        assert len(world.drive.created_bodies) == 2  # root and one retained partial document
        if failure_case == "creation":
            _assert_creation_failure_reconciles_without_repopulating(world, retained)


def test_publication_is_receipted_literal_and_a_republish_preserves_external_notes(tmp_path: Path) -> None:
    with _publication_world(tmp_path, "none") as world:
        published = world.publish()
        assert published.state is PublicationState.PUBLISHED
        assert world.receipts.load_publication(world.publication.publication_id) == published
        identifier = published.artifacts[0].artifact_id
        assert world.drive.created_bodies[-1]["name"] == world.plan.metadata.document_title
        assert str(world.publication.publication_id) not in world.plan.metadata.document_title
        assert "2026-10-05 00:00 UTC" in world.plan.metadata.document_title
        assert tuple(world.sheets.tabs[identifier]) == tuple(tab.value for tab in world.plan.tabs)
        assert world.sheets.value_bodies[0]["valueInputOption"] == "RAW"
        assert world.sheets.cells[identifier][("Detalle", 5, 11)] == '=IMPORTXML("https://example.invalid", "x")'
        assert world.sheets.cells[identifier][("Cálculos", 5, 4)] == 99.75
        assert world.sheets.cells[identifier][("Cálculos", 5, 5)] == "99.75"
        assert world.sheets.read_ranges
        assert all(":" not in address and not address.startswith("'Entradas'") for address in world.sheets.read_ranges)
        world.sheets.cells[identifier][("Entradas", 5, 2)] = "User review note"
        world.sheets.calls.clear()
        assert world.publish() == published
        assert world.sheets.calls == []
        assert world.sheets.cells[identifier][("Entradas", 5, 2)] == "User review note"
