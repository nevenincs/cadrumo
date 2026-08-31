"""Authenticated cryptographic record contract for an acceleration receipt.

The profile receipt lifecycle owns keychain coordination and local-record
publication.  This module owns the immutable AEAD record it publishes: its
strict model, metadata binding, wrap, unwrap, and idle-deadline rewrap.
Consumers that need the cryptographic contract import it directly rather than
reaching through the lifecycle coordinator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import canonical_json_bytes
from .....core.identity import canonical_profile_bucket_id
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.time import validate_utc_aware
from ..crypto.aead import KEY_SIZE, EncryptedBlob, decrypt_record, encrypt_record
from ..errors import DecryptionError, EncryptionError
from .zeroise import zeroise as _zeroise

PROFILE_SESSION_SCHEMA_VERSION: Final[int] = 2
"""Current persisted-session record schema version.

A record carrying any other version is a revocable cache from another build:
resume deletes it and refuses so the operator re-logs-in.  This cache is not a
durability-preserved product record.
"""

PROFILE_SESSION_KEY_BYTES: Final[int] = 32
"""Exact AES-256 key width used for the OS-keychain receipt secret."""

_NONCE_BYTES: Final[int] = 12
_TAG_BYTES: Final[int] = 16
_AAD_PREFIX: Final[str] = "cadrumo.profile-session.v2"
_STORAGE_DECRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_decryption"
_STORAGE_ENCRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_encryption"


def _encryption_error(message: str) -> EncryptionError:
    return EncryptionError(message, translated_message=_STORAGE_ENCRYPTION_MESSAGE_KEY)


def validate_profile_session_metadata(
    *,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    issued_at: datetime,
) -> datetime:
    """Validate immutable receipt metadata before durable coordination."""
    canonical_profile_bucket_id(profile_id)
    if custody_generation < 1:
        raise _encryption_error("custody_generation must be a strict positive integer")
    if not dek_epoch:
        raise _encryption_error("dek_epoch must be non-empty")
    return validate_utc_aware(issued_at)


class PersistedProfileSession(BaseModel):
    """Frozen session-wrapped-DEK record for one bucket's profile receipt."""

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID
    custody_generation: int = Field(ge=1)
    dek_epoch: str = Field(min_length=1, max_length=128)
    issued_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    nonce: bytes = Field(min_length=_NONCE_BYTES, max_length=_NONCE_BYTES)
    ciphertext: bytes = Field(min_length=KEY_SIZE, max_length=KEY_SIZE)
    tag: bytes = Field(min_length=_TAG_BYTES, max_length=_TAG_BYTES)

    @field_validator("issued_at", "idle_deadline", "absolute_deadline")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        """Reject naive or non-UTC deadlines at the model boundary."""
        return validate_utc_aware(value)


def _associated_data(
    *,
    schema_version: int,
    profile_id: UUID,
    session_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    issued_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
) -> bytes:
    """Compose canonical AEAD associated data for one receipt record."""
    payload = canonical_json_bytes(
        {
            "absolute_deadline": absolute_deadline.isoformat(),
            "custody_generation": custody_generation,
            "dek_epoch": dek_epoch,
            "idle_deadline": idle_deadline.isoformat(),
            "issued_at": issued_at.isoformat(),
            "profile_id": canonical_profile_bucket_id(profile_id),
            "schema_version": schema_version,
            "session_id": str(session_id),
        },
    )
    return f"{_AAD_PREFIX}:".encode(_UTF_8_ENCODING) + payload


def wrap_profile_session_dek(
    *,
    session_key: bytes,
    dek: bytes,
    profile_id: UUID,
    session_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    issued_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
) -> PersistedProfileSession:
    """Wrap ``dek`` under ``session_key`` with all metadata bound as AAD."""
    if len(session_key) != PROFILE_SESSION_KEY_BYTES:
        raise _encryption_error(f"session_key must be exactly {PROFILE_SESSION_KEY_BYTES} bytes")
    if len(dek) != KEY_SIZE:
        raise _encryption_error(f"dek must be exactly {KEY_SIZE} bytes")
    issued_at = validate_profile_session_metadata(
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        issued_at=issued_at,
    )
    idle_deadline = validate_utc_aware(idle_deadline)
    absolute_deadline = validate_utc_aware(absolute_deadline)
    if idle_deadline > absolute_deadline:
        raise _encryption_error("idle_deadline must not exceed absolute_deadline")

    aad = _associated_data(
        schema_version=PROFILE_SESSION_SCHEMA_VERSION,
        profile_id=profile_id,
        session_id=session_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        issued_at=issued_at,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
    )
    try:
        blob = encrypt_record(dek, key=session_key, associated_data=aad)
    except EncryptionError as exc:
        exc.translated_message = _STORAGE_ENCRYPTION_MESSAGE_KEY
        raise
    return PersistedProfileSession(
        schema_version=PROFILE_SESSION_SCHEMA_VERSION,
        profile_id=profile_id,
        session_id=session_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        issued_at=issued_at,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
        nonce=blob.nonce,
        ciphertext=blob.ciphertext[:KEY_SIZE],
        tag=blob.ciphertext[KEY_SIZE:],
    )


def unwrap_profile_session_dek(*, session_key: bytes, record: PersistedProfileSession) -> bytearray:
    """Recover a wipeable 32-byte DEK after authenticating every metadata field."""
    if len(session_key) != PROFILE_SESSION_KEY_BYTES:
        raise _encryption_error(f"session_key must be exactly {PROFILE_SESSION_KEY_BYTES} bytes")
    aad = _associated_data(
        schema_version=record.schema_version,
        profile_id=record.profile_id,
        session_id=record.session_id,
        custody_generation=record.custody_generation,
        dek_epoch=record.dek_epoch,
        issued_at=record.issued_at,
        idle_deadline=record.idle_deadline,
        absolute_deadline=record.absolute_deadline,
    )
    blob = EncryptedBlob(nonce=record.nonce, ciphertext=record.ciphertext + record.tag)
    try:
        return bytearray(decrypt_record(blob, key=session_key, associated_data=aad))
    except DecryptionError as exc:
        exc.translated_message = _STORAGE_DECRYPTION_MESSAGE_KEY
        raise


def advance_profile_session_idle_deadline(
    *,
    record: PersistedProfileSession,
    session_key: bytes,
    new_idle_deadline: datetime,
) -> PersistedProfileSession:
    """Re-wrap a receipt with a clamped idle deadline and a fresh nonce."""
    clamped = min(validate_utc_aware(new_idle_deadline), record.absolute_deadline)
    dek_buffer = unwrap_profile_session_dek(session_key=session_key, record=record)
    try:
        return wrap_profile_session_dek(
            session_key=session_key,
            dek=bytes(dek_buffer),
            profile_id=record.profile_id,
            session_id=record.session_id,
            custody_generation=record.custody_generation,
            dek_epoch=record.dek_epoch,
            issued_at=record.issued_at,
            idle_deadline=clamped,
            absolute_deadline=record.absolute_deadline,
        )
    finally:
        _zeroise(dek_buffer)


__all__ = [
    "PROFILE_SESSION_KEY_BYTES",
    "PROFILE_SESSION_SCHEMA_VERSION",
    "PersistedProfileSession",
    "advance_profile_session_idle_deadline",
    "unwrap_profile_session_dek",
    "validate_profile_session_metadata",
    "wrap_profile_session_dek",
]
