"""Ordinary content admission enforces acknowledged organizational placement."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .....application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError, OutboundStorageNetworkError
from ..artifact_admission import GoogleArtifactAdmission, artifact_mime_type, creation_properties
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from ..root_layout import GoogleRootLayout
from .drive_files_server import drive_files_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]
_PROFILE = UUID("7548e900-7987-4251-8d55-861e2b7dc37c")


def _root() -> ArtifactCreationReceipt:
    return ArtifactCreationReceipt(
        profile_id=_PROFILE,
        root_folder_id="retained-root",
        artifact_id="retained-root",
        creation_id=uuid4(),
        kind=ManagedArtifactKind.ROOT,
    )


def _entry(receipt: ArtifactCreationReceipt) -> dict[str, object]:
    return {
        "id": receipt.artifact_id,
        "parents": [receipt.parent_id or "root"],
        "mimeType": artifact_mime_type(receipt.kind),
        "trashed": False,
        "appProperties": creation_properties(
            profile_id=receipt.profile_id,
            creation_id=receipt.creation_id,
            kind=receipt.kind,
            root_folder_id=None if receipt.kind is ManagedArtifactKind.ROOT else receipt.root_folder_id,
        ),
    }


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("root", "parents", ["outside"]),
        ("parent", "parents", ["outside"]),
        ("parent", "trashed", True),
        ("parent", "mimeType", "application/vnd.google-apps.shortcut"),
        ("parent", "appProperties", {}),
    ],
)
def test_moved_or_unowned_placement_refuses_descendant_access(
    tmp_path: Path, target: str, field: str, value: object
) -> None:
    root = _root()
    child = ArtifactCreationReceipt(
        profile_id=_PROFILE,
        root_folder_id=root.artifact_id,
        artifact_id="retained-sheet",
        parent_id=root.artifact_id,
        creation_id=uuid4(),
        kind=ManagedArtifactKind.REVIEW_SHEET,
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint(entries=(_entry(root), _entry(child))) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        receipts.record(root)
        receipts.record(child)
        parent_id = GoogleRootLayout(
            drive.service,
            profile.repository,
            root=root,
            commit=lambda save, *, changed: save(),
            before_handoff=lambda action, *, writes=False: None,
            acknowledged=lambda action, *, writes=False: None,
        ).organize()
        admission = GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts)
        assert admission.require(child.artifact_id) == child
        identifier = root.artifact_id if target == "root" else parent_id
        next(entry for entry in drive.entries if entry["id"] == identifier)[field] = value
        drive.calls.clear()
        with pytest.raises(OutboundStorageConflictError):
            admission.require(child.artifact_id)
        assert drive.calls == ["files.get"] * (2 if target == "root" else 3)
        assert receipts.load(root.artifact_id) == root


def test_lost_move_response_blocks_content_until_exact_reconciliation(tmp_path: Path) -> None:
    root = _root()
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint(entries=(_entry(root),)) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        receipts.record(root)
        layout = GoogleRootLayout(
            drive.service,
            profile.repository,
            root=root,
            commit=lambda save, *, changed: save(),
            before_handoff=lambda action, *, writes=False: None,
            acknowledged=lambda action, *, writes=False: None,
        )
        drive.update_statuses.append(503)
        with pytest.raises(OutboundStorageNetworkError):
            layout.organize()
        admission = GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts)
        with pytest.raises(OutboundStorageConflictError):
            admission.require(root.artifact_id)
        updates = drive.calls.count("files.update")
        layout.organize()
        assert admission.require(root.artifact_id) == root
        assert drive.calls.count("files.update") == updates == 1
        drive.calls.clear()
        with pytest.raises(OutboundStorageConflictError):
            admission.require("sibling-profile-root")
        assert drive.calls == []
