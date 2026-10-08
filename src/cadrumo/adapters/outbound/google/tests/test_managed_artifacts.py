"""Real HTTP requests and encrypted custody for managed creation and binary integrity."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .....application.export.managed_artifact_ports import ManagedArtifactKind, ManagedArtifactPurpose
from .....core.hashing import sha256_hex
from ....persistence.storage.errors import SecureObjectRevisionConflictError
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageConflictError, OutboundStorageIntegrityError, OutboundStorageNetworkError
from ..artifact_admission import GoogleArtifactAdmission
from ..artifact_receipt_store import GoogleArtifactReceiptStore
from ..managed_artifacts import ManagedGoogleArtifacts
from ..root_folder import ensure_root_folder
from .drive_files_server import drive_files_endpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]
_PROFILE = UUID("3d2a9c41-7f5e-4b0a-9c1d-5e8f7a6b4c32")


@pytest.mark.parametrize("duplicate", [False, True])
def test_lost_create_response_reconciles_only_one_intent_match_without_replay(tmp_path: Path, duplicate: bool) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint() as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        root_id = ensure_root_folder(drive.service, profile=str(_PROFILE), receipts=receipts)
        root = receipts.load(root_id)
        assert root is not None
        transport = ManagedGoogleArtifacts(
            GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts), receipts=receipts
        )
        publication_id = uuid4()
        parent = transport.admit(root, purpose=ManagedArtifactPurpose.PUBLICATION)
        drive.create_statuses.append(503)
        with pytest.raises(OutboundStorageNetworkError):
            transport.create(
                parent, name="unknown review", kind=ManagedArtifactKind.REVIEW_SHEET, publication_id=publication_id
            )
        assert len(drive.created_bodies) == 2
        identifier = str(drive.entries[-1]["id"])
        assert receipts.load(identifier) is None
        if duplicate:
            drive.entries.append({**drive.entries[-1], "id": "copied-identity"})
        drive.calls.clear()
        reconciliation = transport.admit(root, purpose=ManagedArtifactPurpose.RECONCILIATION)
        if duplicate:
            with pytest.raises(OutboundStorageConflictError):
                transport.reconcile_creation(
                    reconciliation,
                    name="unknown review",
                    kind=ManagedArtifactKind.REVIEW_SHEET,
                    publication_id=publication_id,
                )
            assert receipts.load(identifier) is None
        else:
            recovered = transport.reconcile_creation(
                reconciliation,
                name="unknown review",
                kind=ManagedArtifactKind.REVIEW_SHEET,
                publication_id=publication_id,
            )
            assert recovered.artifact_id == identifier
            assert receipts.load(identifier) == recovered
        assert set(drive.calls) <= {"files.get", "files.list"}
        assert len(drive.created_bodies) == 2


def test_native_creation_and_binary_population_preserve_prior_artifacts(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint() as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        root_id = ensure_root_folder(drive.service, profile=str(_PROFILE), receipts=receipts)
        root = receipts.load(root_id)
        assert root is not None
        transport = ManagedGoogleArtifacts(
            GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts), receipts=receipts
        )
        parent = transport.admit(root, purpose=ManagedArtifactPurpose.PUBLICATION)
        publication_id = uuid4()
        sheet = transport.create(
            parent, name="Review 1", kind=ManagedArtifactKind.REVIEW_SHEET, publication_id=publication_id
        )
        assert drive.created_bodies[-1]["parents"] == [root_id]
        assert drive.created_bodies[-1]["mimeType"] == "application/vnd.google-apps.spreadsheet"
        assert sheet.publication_id == publication_id
        creates = len(drive.created_bodies)
        with pytest.raises(SecureObjectRevisionConflictError):
            transport.create(
                parent, name="Review 1", kind=ManagedArtifactKind.REVIEW_SHEET, publication_id=publication_id
            )
        assert len(drive.created_bodies) == creates
        binary = transport.create(
            parent, name="Encrypted review", kind=ManagedArtifactKind.CIPHERTEXT, publication_id=uuid4()
        )
        payload = b"synthetic-ciphertext-envelope"
        digest = sha256_hex(payload)
        writer = transport.admit(binary, purpose=ManagedArtifactPurpose.PUBLICATION)
        transport.write_bytes(writer, payload, expected_digest=digest)
        reader = transport.admit(binary, purpose=ManagedArtifactPurpose.BACKUP_INTEGRITY)
        assert transport.read_bytes(reader, expected_digest=digest) == payload
        with pytest.raises(SecureObjectRevisionConflictError):
            transport.write_bytes(writer, b"replacement", expected_digest=sha256_hex(b"replacement"))
        assert drive.payloads[binary.artifact_id] == payload
        assert receipts.load(sheet.artifact_id) == sheet
        assert receipts.load(binary.artifact_id) == binary


def test_binary_digest_mismatch_and_movement_refuse_before_content(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        drive_files_endpoint() as drive,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        root_id = ensure_root_folder(drive.service, profile=str(_PROFILE), receipts=receipts)
        root = receipts.load(root_id)
        assert root is not None
        transport = ManagedGoogleArtifacts(
            GoogleArtifactAdmission(drive.service, profile_id=_PROFILE, root=root, receipts=receipts), receipts=receipts
        )
        parent = transport.admit(root, purpose=ManagedArtifactPurpose.PUBLICATION)
        binary = transport.create(
            parent, name="ciphertext", kind=ManagedArtifactKind.CIPHERTEXT, publication_id=uuid4()
        )
        writer = transport.admit(binary, purpose=ManagedArtifactPurpose.PUBLICATION)
        drive.calls.clear()
        with pytest.raises(OutboundStorageIntegrityError):
            transport.write_bytes(writer, b"wrong", expected_digest="0" * 64)
        assert drive.calls == []
        drive.entries[-1]["parents"] = ["unrelated-folder"]
        with pytest.raises(OutboundStorageConflictError):
            transport.write_bytes(writer, b"x", expected_digest=sha256_hex(b"x"))
        assert drive.calls == ["files.get"]
