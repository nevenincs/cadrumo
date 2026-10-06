"""New publications, literal text, retained failures and preservation of external notes."""

from asyncio import CancelledError
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from .....application.export.managed_artifact_ports import ManagedArtifactKind, ManagedArtifactPurpose
from .....application.export.publication_receipt import PublicationFailure, PublicationReceipt, PublicationState
from .....application.export.review_snapshot import ReviewSnapshotContent, seal_review_snapshot
from .....application.storage.calc_sheets.review_workbook import build_review_workbook
from .....application.storage.calc_sheets.tests.review_fixture import review_label, review_snapshot
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError, OutboundStorageNetworkError
from ..artifact_admission import GoogleArtifactAdmission
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from ..calc_sheets_apply import publish_review_plan
from ..managed_artifacts import ManagedGoogleArtifacts
from ..root_folder import ensure_root_folder
from .drive_files_server import drive_files_endpoint
from .review_sheets_server import review_sheets_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("failure_case", ["none", "population", "baseline", "movement", "cancelled", "creation"])
def test_publication_is_receipted_literal_and_never_repopulates_a_retry(tmp_path: Path, failure_case: str) -> None:
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
        if failure_case != "none":
            errors = {
                "population": OutboundStorageNetworkError,
                "baseline": OutboundStorageConflictError,
                "movement": OutboundStorageConflictError,
                "cancelled": CancelledError,
                "creation": OutboundStorageNetworkError,
            }
            with pytest.raises(errors[failure_case]):
                publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service)
            retained = receipts.load_publication(publication.publication_id)
            assert retained is not None
            assert retained.state is (
                PublicationState.UNCERTAIN if failure_case == "creation" else PublicationState.PARTIAL
            )
            assert len(retained.artifacts) == (0 if failure_case == "creation" else 1)
            assert (
                retained.failure
                is {
                    "population": PublicationFailure.POPULATION,
                    "baseline": PublicationFailure.INTEGRITY,
                    "movement": PublicationFailure.POPULATION,
                    "cancelled": PublicationFailure.CANCELLED,
                    "creation": PublicationFailure.CREATE_UNKNOWN,
                }[failure_case]
            )
            if failure_case in {"movement", "cancelled"}:
                assert sheets.read_ranges == []
            sheets.calls.clear()
            with pytest.raises(OutboundStorageConflictError):
                publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service)
            assert sheets.calls == []
            assert len(drive.created_bodies) == 2  # root and one retained partial document
            if failure_case == "creation":
                parent = artifacts.admit(root, purpose=ManagedArtifactPurpose.RECONCILIATION)
                recovered = artifacts.reconcile_creation(
                    parent,
                    name=f"{plan.metadata.title} [{publication.publication_id}]",
                    kind=ManagedArtifactKind.REVIEW_SHEET,
                    publication_id=publication.publication_id,
                )
                assert recovered.artifact_id == drive.entries[-1]["id"]
                assert receipts.load_publication(publication.publication_id) == retained
                assert sheets.calls == []
                with pytest.raises(OutboundStorageConflictError):
                    publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service)
                assert len(drive.created_bodies) == 2
                assert sheets.calls == []
            return
        published = publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service)
        assert published.state is PublicationState.PUBLISHED
        assert receipts.load_publication(publication.publication_id) == published
        identifier = published.artifacts[0].artifact_id
        assert tuple(sheets.tabs[identifier]) == tuple(tab.value for tab in plan.tabs)
        assert sheets.value_bodies[0]["valueInputOption"] == "RAW"
        assert sheets.cells[identifier][("Detalle", 5, 11)] == '=IMPORTXML("https://example.invalid", "x")'
        assert sheets.cells[identifier][("Cálculos", 5, 4)] == 99.75
        assert sheets.cells[identifier][("Cálculos", 5, 5)] == "99.75"
        assert sheets.read_ranges
        assert all(":" not in address and not address.startswith("'Entradas'") for address in sheets.read_ranges)
        sheets.cells[identifier][("Entradas", 5, 2)] = "User review note"
        sheets.calls.clear()
        assert (
            publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service) == published
        )
        assert sheets.calls == []
        assert sheets.cells[identifier][("Entradas", 5, 2)] == "User review note"
