"""Real-authority contracts for the concrete profile-custody adapter."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from .....application.user_profile.custody_ports import (
    ProfilePassphraseEncryptedRecord,
    ProfileRecordCryptoError,
    ProfileRecordEncryptedBlob,
)
from .. import build_profile_custody_port
from ..custody import ProfileCustodyCapsuleLabel, ProfileLabelHead, ProfileLabelHeadRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_local_record_store_preserves_atomic_compare_and_clear_semantics(tmp_path: Path) -> None:
    store = build_profile_custody_port().local_record_store()
    record = tmp_path / "local" / "record.json"
    store.ensure_directory(record.parent)

    store.write(record, b"first", publish_once=True)
    assert store.read(record, maximum_bytes=16) == b"first"
    store.compare_and_replace(record, expected=b"first", replacement=b"second", maximum_bytes=16)
    assert store.read_optional(record, maximum_bytes=16) == b"second"
    store.compare_and_clear(record, expected=b"second", maximum_bytes=16)
    assert store.read_optional(record, maximum_bytes=16) is None


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
        crypto.open_with_passphrase(
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
        crypto.open_with_passphrase(
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
    repository.begin_advance(
        current_head=initial_head,
        current_label=initial,
        replacement_label=replacement,
    )

    recovered_head = port.verify_or_recover_initial_label_head(
        label=replacement,
        source_witness="sha256:" + "d" * 64,
        root=tmp_path,
    )

    assert recovered_head.label_revision == 2
    assert repository.verify(label=replacement) == recovered_head
    assert not repository.pending_path(profile_id).exists()
