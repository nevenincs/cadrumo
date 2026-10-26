"""Creation custody and fresh ancestry checks against a local HTTP Drive tree."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .....application.export.managed_artifact_ports import (
    ArtifactCreationReceipt,
    ManagedArtifactKind,
    ManagedArtifactPurpose,
)
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError
from ..artifact_admission import GoogleArtifactAdmission, artifact_mime_type, creation_properties
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from .drive_files_server import drive_files_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]
_PROFILE = UUID("3d2a9c41-7f5e-4b0a-9c1d-5e8f7a6b4c32")


def _receipt(identifier: str, kind: ManagedArtifactKind, parent: str | None = None) -> ArtifactCreationReceipt:
    return ArtifactCreationReceipt(
        profile_id=_PROFILE,
        root_folder_id="managed-root",
        artifact_id=identifier,
        parent_id=parent,
        creation_id=uuid4(),
        kind=kind,
    )


def _entry(receipt: ArtifactCreationReceipt) -> dict[str, object]:
    return {
        "id": receipt.artifact_id,
        "mimeType": artifact_mime_type(receipt.kind),
        "trashed": False,
        "parents": [receipt.parent_id or "outside-root-anchor"],
        "appProperties": creation_properties(
            profile_id=receipt.profile_id,
            creation_id=receipt.creation_id,
            kind=receipt.kind,
            root_folder_id=None if receipt.kind is ManagedArtifactKind.ROOT else receipt.root_folder_id,
        ),
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("parents", ["outside"]),
        ("trashed", True),
        ("mimeType", "application/vnd.google-apps.shortcut"),
        ("appProperties", {}),
    ],
)
def test_invalid_child_refused_before_ancestor_or_content_access(tmp_path: Path, field: str, value: object) -> None:
    root = _receipt("managed-root", ManagedArtifactKind.ROOT)
    child = _receipt("sheet", ManagedArtifactKind.REVIEW_SHEET, root.artifact_id)
    altered = {**_entry(child), field: value}
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint(entries=(_entry(root), altered)) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        for receipt in (root, child):
            receipts.record(receipt)
        admission = GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts)
        with pytest.raises(OutboundStorageConflictError):
            admission.require(child.artifact_id)
        assert drive.calls == ["files.get"]


def test_unknown_copy_and_wrong_profile_make_no_provider_call(tmp_path: Path) -> None:
    root = _receipt("managed-root", ManagedArtifactKind.ROOT)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint(entries=(_entry(root), {**_entry(root), "id": "copy"})) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        receipts.record(root)
        admission = GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts)
        with pytest.raises(OutboundStorageConflictError):
            admission.require("copy")
        foreign = GoogleArtifactAdmission(drive.service, profile_id=uuid4(), root=root, receipts=receipts)
        with pytest.raises(OutboundStorageConflictError):
            foreign.require(root.artifact_id)
        assert drive.calls == []


def test_each_admission_rechecks_ancestor_and_never_walks_outside_root(tmp_path: Path) -> None:
    root = _receipt("managed-root", ManagedArtifactKind.ROOT)
    folder = _receipt("folder", ManagedArtifactKind.FOLDER, root.artifact_id)
    child = _receipt("sheet", ManagedArtifactKind.REVIEW_SHEET, folder.artifact_id)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint(entries=tuple(_entry(item) for item in (root, folder, child))) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        for receipt in (root, folder, child):
            receipts.record(receipt)
        admission = GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts)
        admitted = admission.admit(child, purpose=ManagedArtifactPurpose.PUBLICATION)
        assert admitted.receipt == child
        assert drive.calls == ["files.get"] * 3
        drive.calls.clear()
        drive.entries[1]["parents"] = ["unknown-outside-folder"]
        with pytest.raises(OutboundStorageConflictError):
            admission.admit(admitted.receipt, purpose=admitted.purpose)
        assert drive.calls == ["files.get"] * 2


def test_known_root_can_move_without_adopting_or_probing_external_ancestors(tmp_path: Path) -> None:
    root = _receipt("managed-root", ManagedArtifactKind.ROOT)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint(entries=(_entry(root),)) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        receipts.record(root)
        admission = GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts)
        assert admission.require(root.artifact_id) == root
        drive.entries[0]["parents"] = ["another-external-folder"]
        assert admission.require(root.artifact_id) == root
        assert drive.calls == ["files.get", "files.get"]
