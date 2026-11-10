"""Real-authority contracts for the concrete profile-custody adapter."""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from uuid import UUID

import pytest

from .....application.user_profile.custody_crypto_contracts import (
    ProfilePassphraseEncryptedRecord,
    ProfileRecordCryptoError,
    ProfileRecordEncryptedBlob,
)
from .....application.user_profile.proof_cancellation import ProfileProofCancellation
from .....core.config import override_settings
from ..crypto.aead import EncryptedBlob, decrypt_record
from ..custody import kdf_process
from ..custody.capsule_records import ProfileCustodyCapsuleLabel
from ..custody.kdf_worker_supervision import SupervisedKdfWorker
from ..custody.label_head_models import ProfileLabelHead
from ..custody.label_head_repository import ProfileLabelHeadRepository
from ..custody.tests.label_head_probe import begin_advance
from ..errors import DecryptionError
from ..profile_custody import build_profile_custody_port
from .passphrase_probe import open_with_passphrase

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SYNTHETIC_PHRASE = "synthetic registration phrase"


def test_local_record_store_preserves_bounded_read_write_and_clear(tmp_path: Path) -> None:
    store = build_profile_custody_port().local_record_store()
    record = tmp_path / "local" / "record.json"
    store.ensure_directory(record.parent)

    store.write(record, b"first", publish_once=True)
    assert store.read(record, maximum_bytes=16) == b"first"
    store.write(record, b"second", publish_once=False)
    assert store.read(record, maximum_bytes=16) == b"second"
    store.clear(record)
    assert not record.exists()


def test_record_crypto_returns_the_application_dto_and_refuses_tampering() -> None:
    crypto = build_profile_custody_port().record_crypto()
    key = bytes(range(32))
    associated_data = b"profile-record:test"

    blob = crypto.encrypt_record(b"payload", key=key, associated_data=associated_data)

    assert type(blob) is ProfileRecordEncryptedBlob
    assert crypto.decrypt_record(blob, key=key, associated_data=associated_data) == b"payload"

    tampered = ProfileRecordEncryptedBlob(
        nonce=blob.nonce,
        ciphertext=blob.ciphertext[:-1] + bytes((blob.ciphertext[-1] ^ 1,)),
    )
    with pytest.raises(ProfileRecordCryptoError, match="decryption failed"):
        crypto.decrypt_record(tampered, key=key, associated_data=associated_data)


def test_profile_and_storage_blob_wire_contracts_round_trip_through_real_crypto() -> None:
    crypto = build_profile_custody_port().record_crypto()
    key = bytes(range(32))
    associated_data = b"profile-record:blob-boundary-parity"

    for plaintext in (b"", b"synthetic profile-record payload"):
        application_blob = crypto.encrypt_record(
            plaintext,
            key=key,
            associated_data=associated_data,
        )
        wire = application_blob.to_wire()

        assert len(wire) == 12 + 16 + len(plaintext)
        application_round_trip = ProfileRecordEncryptedBlob.from_wire(wire)
        storage_round_trip = EncryptedBlob.from_wire(wire)

        assert application_round_trip == application_blob
        assert application_round_trip.to_wire() == wire
        assert storage_round_trip.to_wire() == wire
        assert (
            crypto.decrypt_record(
                application_round_trip,
                key=key,
                associated_data=associated_data,
            )
            == plaintext
        )
        assert (
            decrypt_record(
                storage_round_trip,
                key=key,
                associated_data=associated_data,
            )
            == plaintext
        )

        if not plaintext:
            assert len(wire) == 28
            with pytest.raises(ProfileRecordCryptoError, match="payload too short"):
                ProfileRecordEncryptedBlob.from_wire(wire[:-1])
            with pytest.raises(DecryptionError, match="payload too short"):
                EncryptedBlob.from_wire(wire[:-1])


def test_passphrase_crypto_returns_the_application_dto_and_refuses_tampering() -> None:
    crypto = build_profile_custody_port().record_crypto()
    associated_data = b"profile-bundle:test"
    sealed = crypto.seal_with_passphrase(
        b"payload",
        passphrase=b"a real operator passphrase 123",
        associated_data=associated_data,
    )

    assert type(sealed) is ProfilePassphraseEncryptedRecord
    assert (
        open_with_passphrase(
            crypto,
            sealed.blob,
            passphrase=b"a real operator passphrase 123",
            parameters=sealed.parameters,
            associated_data=associated_data,
        )
        == b"payload"
    )

    tampered = ProfileRecordEncryptedBlob(
        nonce=sealed.blob.nonce,
        ciphertext=sealed.blob.ciphertext[:-1] + bytes((sealed.blob.ciphertext[-1] ^ 1,)),
    )
    with pytest.raises(ProfileRecordCryptoError, match="decryption failed"):
        open_with_passphrase(
            crypto,
            tampered,
            passphrase=b"a real operator passphrase 123",
            parameters=sealed.parameters,
            associated_data=associated_data,
        )


def test_label_head_caller_explicitly_recovers_then_verifies_or_publishes(tmp_path: Path) -> None:
    """The adapter composes explicit repository operations for its port contract."""
    port = build_profile_custody_port()
    profile_id = UUID("ba7ecf09-72af-4b38-8c59-03119fdc477c")
    initial = ProfileCustodyCapsuleLabel.create(profile_id=profile_id, label="Initial label")

    initial_head = port.verify_or_recover_initial_label_head(
        label=initial,
        source_witness="sha256:" + "d" * 64,
        root=tmp_path,
    )
    assert isinstance(initial_head, ProfileLabelHead)
    assert initial_head.label_revision == 1
    assert (
        port.verify_or_recover_initial_label_head(
            label=initial,
            source_witness="sha256:" + "d" * 64,
            root=tmp_path,
        )
        == initial_head
    )

    replacement = ProfileCustodyCapsuleLabel.create(
        profile_id=profile_id,
        label="Replacement label",
        label_revision=2,
        previous_label_digest=initial.content_digest,
    )
    repository = ProfileLabelHeadRepository(root=tmp_path)
    begin_advance(repository, current_head=initial_head, current_label=initial, replacement_label=replacement)

    recovered_head = port.verify_or_recover_initial_label_head(
        label=replacement,
        source_witness="sha256:" + "d" * 64,
        root=tmp_path,
    )

    assert recovered_head.label_revision == 2
    assert repository.verify(label=replacement) == recovered_head
    assert not repository.pending_path(profile_id).exists()


def test_registration_wraps_in_a_child_prewarmed_for_this_mint_and_leaves_none_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched: list[subprocess.Popen[bytes]] = []
    adopted: list[bool] = []
    launch_process = kdf_process.launch_worker_process
    adopt = SupervisedKdfWorker.adopt

    def observe_launch(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        process = launch_process(command, launch_kwargs)
        launched.append(process)
        return process

    def observe_adopt(
        worker: SupervisedKdfWorker, *, deadline: float, cancellation: ProfileProofCancellation | None = None
    ) -> bool:
        verdict = adopt(worker, deadline=deadline, cancellation=cancellation)
        adopted.append(verdict)
        return verdict

    monkeypatch.setattr(kdf_process, "launch_worker_process", observe_launch)
    monkeypatch.setattr(SupervisedKdfWorker, "adopt", observe_adopt)
    profile_id = UUID("00000000-0000-4000-8000-0000000000a1")
    dek = bytes(range(32))
    with override_settings(cadrumo_storage_root=tmp_path, cadrumo_profile_kdf_measure_calibration=False):
        port = build_profile_custody_port()
        material = port.create_registration_material(
            profile_id=profile_id,
            password=_SYNTHETIC_PHRASE,
            dek=dek,
            dek_epoch=base64.b64encode(b"e" * 16).decode("ascii"),
            salt=b"s" * 16,
            predecessor=None,
        )
        assert adopted == [True], "the wrap ran in the spare launched for this mint"
        assert len(launched) == 1, "no successor is launched after the mint's last derivation"
        assert all(process.poll() is not None for process in launched), "nothing outlives the mint"

        unlocked = port.unlock_password(material, password=_SYNTHETIC_PHRASE)
    assert unlocked.dek == dek
