"""Typed BIP-39 recovery facade for the per-bucket unlock pipeline.

The substrate's BIP-39 mnemonic encoding, HKDF-derived recovery KEK, and
AES-256-GCM wrap of the master DEK live in `_recovery.py`. This module
exposes a typed boundary over those primitives so callers consume and
produce the strict pydantic v2 records (`RecoveryRecord` for the
on-disk envelope, `BucketSession` for the live in-memory state)
without reaching into the substrate. The internals never leave
`_recovery.py`.

`mint_recovery_envelope` is called at enrollment: it generates a fresh
24-word BIP-39 mnemonic, derives the recovery KEK from the entropy,
wraps the supplied DEK under that KEK, and returns the `RecoveryRecord`
+ the plaintext mnemonic (the only in-memory copy; the caller arranges
for the operator to copy it down).

`unwrap_recovery_envelope` is called at recovery: it accepts the
mnemonic the operator typed, decodes the entropy, derives the recovery
KEK, and decrypts the wrapped DEK from the `RecoveryRecord`. The
plaintext mnemonic is never persisted.

`open_session_from_recovery` composes `unwrap_recovery_envelope` with
`BucketSession.open` so the recovery-flow CLI verb yields a live
session the wizard can re-wrap under a fresh passphrase-derived KEK.
"""

from __future__ import annotations

import base64
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..bucket._errors import RecoveryVerificationError
from ..crypto._crypto import EncryptedBlob
from ..errors import DecryptionError
from ._bucket_session import BucketSession
from ._recovery import (
    RecoveryKey,
    WrappedMasterKey,
    decode_mnemonic,
    generate_recovery_key,
    unwrap_master_key,
    wrap_master_key,
)
from ._recovery_record import RecoveryRecord

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_GCM_TAG_BYTES = 16
_HKDF_INFO = "aeat.recovery-key.master-wrap.v1"


class MintedRecovery(BaseModel):
    """In-memory result of a recovery enrollment.

    The mnemonic is the only handle on the recovery KEK; the caller
    arranges for the operator to copy it before this record falls out
    of scope.
    """

    model_config = _STRICT_FROZEN

    envelope: RecoveryRecord
    mnemonic: str


def _envelope_from_blob(blob: EncryptedBlob, created_at: datetime) -> RecoveryRecord:
    """Split the GCM wire shape into the `RecoveryRecord` field set."""

    ciphertext_with_tag = blob.ciphertext
    ciphertext = ciphertext_with_tag[:-_GCM_TAG_BYTES]
    tag = ciphertext_with_tag[-_GCM_TAG_BYTES:]
    return RecoveryRecord(
        wrapped_dek_b64=base64.b64encode(ciphertext).decode("ascii"),
        nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
        tag_b64=base64.b64encode(tag).decode("ascii"),
        mnemonic_word_count=24,
        hkdf_info=_HKDF_INFO,
        created_at=created_at,
    )


def _blob_from_envelope(envelope: RecoveryRecord) -> EncryptedBlob:
    """Re-assemble an `EncryptedBlob` from the typed envelope fields."""

    nonce = base64.b64decode(envelope.nonce_b64.encode("ascii"), validate=True)
    ciphertext = base64.b64decode(envelope.wrapped_dek_b64.encode("ascii"), validate=True)
    tag = base64.b64decode(envelope.tag_b64.encode("ascii"), validate=True)
    return EncryptedBlob(nonce=nonce, ciphertext=ciphertext + tag)


def mint_recovery_envelope(*, dek: bytes, created_at: datetime) -> MintedRecovery:
    """Mint a fresh recovery envelope wrapping `dek`.

    Returns a `MintedRecovery` carrying the typed `RecoveryRecord` and
    the 24-word mnemonic the operator must record. The mnemonic is the
    only handle on the recovery KEK; this function does NOT persist it.
    """

    recovery_key: RecoveryKey = generate_recovery_key()
    wrapped: WrappedMasterKey = wrap_master_key(master_key=dek, recovery_key=recovery_key)
    blob = wrapped.to_blob()
    envelope = _envelope_from_blob(blob, created_at=created_at)
    return MintedRecovery(envelope=envelope, mnemonic=recovery_key.mnemonic)


def unwrap_recovery_envelope(*, envelope: RecoveryRecord, mnemonic: str) -> bytes:
    """Decode `mnemonic` and unwrap `envelope` to recover the 32-byte DEK.

    Raises:
        RecoveryVerificationError: If the mnemonic does not decode or
            the AEAD tag check fails. The error never echoes the typed
            words; only the position of any decoding failure surfaces
            (per the `decode_mnemonic` contract).
    """

    try:
        entropy = decode_mnemonic(mnemonic)
    except Exception as exc:  # ValueError / StorageValidationError surface here
        raise RecoveryVerificationError(str(exc)) from exc

    blob = _blob_from_envelope(envelope)
    wrapped = WrappedMasterKey.from_blob(blob)
    try:
        return unwrap_master_key(wrapped=wrapped, recovery_key_bytes=entropy)
    except DecryptionError as exc:
        raise RecoveryVerificationError(
            "recovery envelope did not decrypt under the supplied mnemonic",
        ) from exc


def verify_recovery_mnemonic(*, envelope: RecoveryRecord, mnemonic: str) -> bool:
    """Return True iff the mnemonic correctly unwraps the envelope.

    Used by profile recovery custody checks. Catches
    `RecoveryVerificationError` and surfaces a boolean so callers can
    render the outcome without leaking detail.
    """

    try:
        unwrap_recovery_envelope(envelope=envelope, mnemonic=mnemonic)
    except RecoveryVerificationError:
        return False
    return True


def open_session_from_recovery(
    *,
    bucket_id: str,
    envelope: RecoveryRecord,
    mnemonic: str,
    kek: bytes,
    idle_minutes: int,
    opened_at: datetime,
) -> BucketSession:
    """Compose mnemonic-unwrap with `BucketSession.open`.

    The caller supplies the freshly-derived passphrase KEK (the
    operator's new passphrase, run through Argon2id under a fresh salt);
    the function unwraps the DEK from the recovery envelope and yields
    a live session bound to `bucket_id`.
    """

    dek = unwrap_recovery_envelope(envelope=envelope, mnemonic=mnemonic)
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=kek,
        dek=dek,
        idle_minutes=idle_minutes,
        opened_at=opened_at,
    )


__all__ = [
    "MintedRecovery",
    "mint_recovery_envelope",
    "open_session_from_recovery",
    "unwrap_recovery_envelope",
    "verify_recovery_mnemonic",
]
