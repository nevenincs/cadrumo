"""Root bootstrap uses encrypted creation evidence and never lists My Drive."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError
from ..artifact_admission import CREATION_MARKER, KIND_MARKER, PROFILE_MARKER
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from ..drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE
from ..root_folder import ensure_root_folder, profile_root_folder_name
from .drive_files_server import drive_files_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_PROFILE = "3d2a9c41-7f5e-4b0a-9c1d-5e8f7a6b4c32"


def test_first_sign_in_creates_and_records_root_without_account_listing(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile, drive_files_endpoint() as drive:
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=UUID(_PROFILE))
        identifier = ensure_root_folder(drive.service, profile=_PROFILE, receipts=receipts)

        assert identifier == "created-1"
        assert drive.calls == ["files.create", "files.get"]
        body = drive.created_bodies[0]
        receipt = receipts.load(identifier)
        assert receipt is not None
        assert body == {
            "name": profile_root_folder_name(_PROFILE),
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["root"],
            "appProperties": {
                OWNERSHIP_KEY: OWNERSHIP_VALUE,
                PROFILE_MARKER: _PROFILE,
                CREATION_MARKER: str(receipt.creation_id),
                KIND_MARKER: "root",
            },
        }
        assert ensure_root_folder(drive.service, profile=_PROFILE, receipts=receipts) == identifier
        assert len(drive.created_bodies) == 1
        assert "files.list" not in drive.calls


def test_same_named_foreign_folder_is_neither_searched_nor_adopted(tmp_path: Path) -> None:
    foreign = {
        "id": "foreign",
        "name": profile_root_folder_name(_PROFILE),
        "parents": ["root"],
        "mimeType": "application/vnd.google-apps.folder",
        "trashed": False,
    }
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile,
        drive_files_endpoint(entries=(foreign,)) as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=UUID(_PROFILE))
        assert ensure_root_folder(drive.service, profile=_PROFILE, receipts=receipts) == "created-1"
        assert drive.entries[0] == foreign
        assert "files.list" not in drive.calls


def test_pending_root_create_is_not_blindly_retried(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile, drive_files_endpoint() as drive:
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=UUID(_PROFILE))
        receipts.begin_root_creation()
        with pytest.raises(OutboundStorageConflictError, match="unknown outcome"):
            ensure_root_folder(drive.service, profile=_PROFILE, receipts=receipts)
        assert drive.calls == []


def test_reused_root_is_rechecked_and_trashed_root_is_not_replaced(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile, drive_files_endpoint() as drive:
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=UUID(_PROFILE))
        ensure_root_folder(drive.service, profile=_PROFILE, receipts=receipts)
        drive.entries[0]["trashed"] = True
        with pytest.raises(OutboundStorageConflictError):
            ensure_root_folder(drive.service, profile=_PROFILE, receipts=receipts)
        assert len(drive.created_bodies) == 1
        assert "files.list" not in drive.calls
