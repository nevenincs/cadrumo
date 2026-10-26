"""Receipt-backed binary provider rechecks a cached ancestor before content access."""

from pathlib import Path
from uuid import UUID

import pytest

from .....core.hashing import sha256_hex
from .....tests.google_credentials import unused_google_credentials
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...google.artifact_receipt_store import GoogleArtifactReceiptStore
from ...google.root_folder import ensure_root_folder
from ...google.tests.drive_files_server import drive_files_endpoint
from .._google_drive import GoogleDriveProvider
from ..errors import OutboundStorageConflictError

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]
_PROFILE = UUID("3d2a9c41-7f5e-4b0a-9c1d-5e8f7a6b4c32")


def test_cached_storage_ancestor_is_rechecked_before_content(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint() as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        root_id = ensure_root_folder(drive.service, profile=str(_PROFILE), receipts=receipts)
        provider = GoogleDriveProvider(
            credentials=unused_google_credentials(),
            root_folder_id=root_id,
            vault_folder_name="vault",
            receipts=receipts,
        )
        provider._service = drive.service
        payload = b"opaque-encrypted-payload"
        metadata = provider.put("synthetic", "a" * 64, payload, content_hash=sha256_hex(payload), label="ciphertext")
        actual, downloaded = provider.get("synthetic", "a" * 64)
        assert actual == payload and downloaded.provider_object_id == metadata.provider_object_id
        namespace_id = provider._namespace_folder_ids["synthetic"]
        namespace = next(entry for entry in drive.entries if entry["id"] == namespace_id)
        namespace["parents"] = ["unrelated-folder"]
        drive.calls.clear()
        with pytest.raises(OutboundStorageConflictError):
            provider.get("synthetic", "a" * 64)
        assert drive.calls == ["files.get"]
        assert drive.payloads[metadata.provider_object_id] == payload
