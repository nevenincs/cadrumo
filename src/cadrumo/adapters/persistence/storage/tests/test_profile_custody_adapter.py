"""Real-authority contracts for the concrete profile-custody adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....application.user_profile.custody_ports import (
    ProfilePassphraseEncryptedRecord,
    ProfileRecordCryptoError,
    ProfileRecordEncryptedBlob,
)
from .. import build_profile_custody_port

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
