"""Known-root relocation preserves identity and reconciles lost responses."""

from pathlib import Path
from uuid import UUID

import pytest

from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError, OutboundStorageNetworkError
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from ..root_folder import ensure_root_folder
from ..root_layout import GoogleRootLayout, load_root_layout
from .drive_files_server import drive_files_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]
_PROFILE = UUID("7548e900-7987-4251-8d55-861e2b7dc37c")


@pytest.mark.parametrize("lost_response", [False, True])
def test_move_preserves_root_children_and_creation_receipt(tmp_path: Path, lost_response: bool) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint() as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        identifier = ensure_root_folder(drive.service, profile=str(_PROFILE), receipts=receipts)
        receipt = receipts.load(identifier)
        assert receipt is not None
        child: dict[str, object] = {"id": "child", "parents": [identifier], "name": "retain-me"}
        drive.entries.append(child.copy())
        operation = GoogleRootLayout(
            drive.service,
            profile.repository,
            root=receipt,
            commit=lambda save, *, changed: save(),
            before_handoff=lambda action, *, writes=False: None,
            acknowledged=lambda action, *, writes=False: None,
        )
        if lost_response:
            drive.update_statuses.append(500)
            with pytest.raises(OutboundStorageNetworkError):
                operation.organize()
            state = load_root_layout(profile.repository, _PROFILE)
            assert state is not None and state.phase == "moving"
        parent = operation.organize()
        assert parent != identifier
        assert next(entry for entry in drive.entries if entry["id"] == identifier)["parents"] == [parent]
        assert next(entry for entry in drive.entries if entry["id"] == "child") == child
        assert receipts.load(identifier) == receipt
        attempt = receipts.root_attempt()
        assert attempt is not None and attempt.receipt == receipt
        assert len(drive.created_bodies) == 2
        assert drive.calls.count("files.update") == 1
        assert operation.organize() == parent
        assert drive.calls.count("files.update") == 1
        assert drive.update_queries[0]["addParents"] == [parent]
        assert drive.update_queries[0]["removeParents"] == ["root"]
        state = load_root_layout(profile.repository, _PROFILE)
        assert state is not None and state.phase == "complete"
        assert "files.get_media" not in drive.calls and "files.delete" not in drive.calls
        next(entry for entry in drive.entries if entry["id"] == identifier)["parents"] = ["foreign"]
        with pytest.raises(OutboundStorageConflictError):
            operation.organize()
        assert drive.calls.count("files.update") == 1
