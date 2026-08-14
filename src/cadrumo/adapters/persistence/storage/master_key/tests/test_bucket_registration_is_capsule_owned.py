"""A bucket's registration is proven by its published profile capsule.

The wrapped data key lives in the separated keystore; whether the bucket is
REGISTERED is a separate question, and the published capsule is its sole
authority. The four arms below are the whole decision table of
:func:`load_or_mint_bucket_dek`.

The second arm is the load-bearing one. A registered bucket whose wrapped
key has gone missing must refuse and send the operator to a backup, never
mint a replacement: the bucket's data was encrypted under the key that
vanished, so minting would write a fresh key over payload nothing can read.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID

import pytest

from ......core.config import Settings
from ...custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
    publish_profile_custody_capsule,
)
from ...errors import MasterKeyMaterialMissingError
from .._master_key_bucket_dek import bucket_dek_path, load_or_mint_bucket_dek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("327b296d-8377-4be0-b13a-ca4d8f692e1d")
_BUCKET_ID = str(_PROFILE_ID)
_KEK = bytes(range(32, 64))
_CAPSULE_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")


def _settings(tmp_path: Path) -> Settings:
    return Settings(cadrumo_local_storage_root=tmp_path)


def _password_envelope() -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=_PROFILE_ID,
        password_generation=1,
        dek_epoch=_EPOCH,
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
            tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
        ),
    )


def _register_bucket(tmp_path: Path) -> None:
    """Publish a real capsule, which is what makes the bucket registered."""
    envelope = _password_envelope()
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=UUID("4f28d1c4-e466-4a08-a25a-ea5925146f36"),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_CAPSULE_DEK),
        data_files={},
        settings=_settings(tmp_path),
    )


def _mint_keystore_dek(tmp_path: Path) -> bytes:
    """Mint the wrapped key through the bootstrap arm, as enrolment does."""
    return load_or_mint_bucket_dek(
        kek=_KEK, storage_root=tmp_path, bucket_id=_BUCKET_ID, allow_bootstrap_mint=True
    )


def test_registered_bucket_with_its_key_unwraps_without_minting(tmp_path: Path) -> None:
    minted = _mint_keystore_dek(tmp_path)
    _register_bucket(tmp_path)

    loaded = load_or_mint_bucket_dek(
        kek=_KEK, storage_root=tmp_path, bucket_id=_BUCKET_ID, allow_bootstrap_mint=False
    )

    assert loaded == minted


def test_registered_bucket_without_its_key_refuses_and_never_mints(tmp_path: Path) -> None:
    """The strand-risk guard: never write a fresh key over unreadable data."""
    _mint_keystore_dek(tmp_path)
    _register_bucket(tmp_path)
    key_file = bucket_dek_path(storage_root=tmp_path, bucket_id=_BUCKET_ID)
    key_file.unlink()

    with pytest.raises(MasterKeyMaterialMissingError) as refusal:
        load_or_mint_bucket_dek(
            kek=_KEK, storage_root=tmp_path, bucket_id=_BUCKET_ID, allow_bootstrap_mint=True
        )

    assert "wrapped DEK is missing" in str(refusal.value)
    assert not key_file.exists()


def test_unregistered_bucket_without_a_key_mints_one(tmp_path: Path) -> None:
    key_file = bucket_dek_path(storage_root=tmp_path, bucket_id=_BUCKET_ID)
    assert not key_file.exists()

    minted = _mint_keystore_dek(tmp_path)

    assert len(minted) == 32
    assert key_file.is_file()


def test_unregistered_bucket_with_a_key_unwraps_it_rather_than_reminting(tmp_path: Path) -> None:
    minted = _mint_keystore_dek(tmp_path)

    again = _mint_keystore_dek(tmp_path)

    assert again == minted
