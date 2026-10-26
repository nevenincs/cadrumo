"""Authenticated cryptographic record contract for an acceleration receipt.

The profile receipt lifecycle owns keychain coordination and local-record
publication.  This module owns the immutable AEAD record it publishes: its
strict model, metadata binding, wrap, unwrap, and idle-deadline rewrap.
Consumers that need the cryptographic contract import it directly rather than
reaching through the lifecycle coordinator.

A receipt binds the human sign-in that minted it: the originating OS login and
the profile's sign-in generation. The generation (a random lineage plus a
counter) is not private and is stored as plaintext metadata. The OS login
locator is: it names a logon session, and on Linux and macOS the OS account.
The receipt therefore stores only ``login_binding``, a SHA-256 commitment to
the login salted with the random session UUID and the profile UUID. The salt
stops a disk reader from linking receipts or precomputing a table, and a
caller holding an expected login can still compare it without any key. Every
plaintext field, including both bindings, is part of the AEAD associated data,
so substituting either one breaks the tag.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import canonical_json_bytes, sha256_hex
from .....core.identity.profile import canonical_profile_bucket_id
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.time.utc import UtcInstant, validate_utc_aware
from ..crypto.aead import EncryptedBlob, decrypt_record, encrypt_record
from ..crypto.aes_gcm import KEY_SIZE
from ..errors import DecryptionError, EncryptionError
from .sign_in_generation import SignInGeneration

PROFILE_SESSION_SCHEMA_VERSION: Final[int] = 3
"""Current persisted-session record schema version.

A record carrying any other version is a revocable cache from another build:
every reader deletes it and refuses so the operator signs in again.  This cache
is not a durability-preserved product record.  Version 3 added the sign-in
binding; the file name and keychain service did not change.
"""

PROFILE_SESSION_LOGIN_ID_MAX_LENGTH: Final[int] = 256
"""Longest OS login locator a receipt can bind, matching the login contract."""

PROFILE_SESSION_KEY_BYTES: Final[int] = 32
"""Exact AES-256 key width used for the OS-keychain receipt secret."""

_NONCE_BYTES: Final[int] = 12
_TAG_BYTES: Final[int] = 16
_AAD_PREFIX: Final[str] = "cadrumo.profile-session.v2"
_LOGIN_BINDING_DOMAIN: Final[bytes] = b"cadrumo.profile-session.login-binding.v1:"
_STORAGE_DECRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_decryption"
_STORAGE_ENCRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_encryption"


def encryption_error(message: str) -> EncryptionError:
    return EncryptionError(message, translated_message=_STORAGE_ENCRYPTION_MESSAGE_KEY)


LoginBindingDigest = Annotated[str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
"""Lowercase hex SHA-256 commitment to one originating OS login."""


def profile_session_login_binding(*, profile_id: UUID, session_id: UUID, login_id: str) -> str:
    """Commit to ``login_id`` for one receipt without storing the locator.

    Raises:
        EncryptionError: When the login locator is empty or over-long.
    """
    if not login_id or len(login_id) > PROFILE_SESSION_LOGIN_ID_MAX_LENGTH:
        raise encryption_error("login_id must be a non-empty OS login locator of bounded length")
    payload = canonical_json_bytes(
        {
            "login_id": login_id,
            "profile_id": canonical_profile_bucket_id(profile_id),
            "session_id": str(session_id),
        },
    )
    return sha256_hex(_LOGIN_BINDING_DOMAIN + payload)


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
        raise encryption_error("custody_generation must be a strict positive integer")
    if not dek_epoch:
        raise encryption_error("dek_epoch must be non-empty")
    return validate_utc_aware(issued_at)


class PersistedProfileSession(BaseModel):
    """Frozen session-wrapped-DEK record for one bucket's profile receipt."""

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID
    custody_generation: int = Field(ge=1)
    dek_epoch: str = Field(min_length=1, max_length=128)
    login_binding: LoginBindingDigest
    sign_in: SignInGeneration
    issued_at: UtcInstant
    idle_deadline: UtcInstant
    absolute_deadline: UtcInstant
    nonce: bytes = Field(min_length=_NONCE_BYTES, max_length=_NONCE_BYTES)
    ciphertext: bytes = Field(min_length=KEY_SIZE, max_length=KEY_SIZE)
    tag: bytes = Field(min_length=_TAG_BYTES, max_length=_TAG_BYTES)


def profile_session_login_matches(*, record: PersistedProfileSession, login_id: str) -> bool:
    """Return whether ``record`` was minted for exactly ``login_id``."""
    if not login_id or len(login_id) > PROFILE_SESSION_LOGIN_ID_MAX_LENGTH:
        return False
    expected = profile_session_login_binding(
        profile_id=record.profile_id,
        session_id=record.session_id,
        login_id=login_id,
    )
    return secrets.compare_digest(expected, record.login_binding)


def _associated_data(
    *,
    schema_version: int,
    profile_id: UUID,
    session_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    login_binding: str,
    sign_in: SignInGeneration,
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
            "login_binding": login_binding,
            "profile_id": canonical_profile_bucket_id(profile_id),
            "schema_version": schema_version,
            "session_id": str(session_id),
            "sign_in_generation": sign_in.generation,
            "sign_in_lineage": str(sign_in.lineage),
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
    login_id: str,
    sign_in: SignInGeneration,
    issued_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
) -> PersistedProfileSession:
    """Wrap ``dek`` under ``session_key`` with all metadata bound as AAD."""
    return _wrap_profile_session_dek(
        session_key=session_key,
        dek=dek,
        profile_id=profile_id,
        session_id=session_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        login_binding=profile_session_login_binding(profile_id=profile_id, session_id=session_id, login_id=login_id),
        sign_in=sign_in,
        issued_at=issued_at,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
    )


def _wrap_profile_session_dek(
    *,
    session_key: bytes,
    dek: bytes,
    profile_id: UUID,
    session_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    login_binding: str,
    sign_in: SignInGeneration,
    issued_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
) -> PersistedProfileSession:
    if len(session_key) != PROFILE_SESSION_KEY_BYTES:
        raise encryption_error(f"session_key must be exactly {PROFILE_SESSION_KEY_BYTES} bytes")
    if len(dek) != KEY_SIZE:
        raise encryption_error(f"dek must be exactly {KEY_SIZE} bytes")
    issued_at = validate_profile_session_metadata(
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        issued_at=issued_at,
    )
    idle_deadline = validate_utc_aware(idle_deadline)
    absolute_deadline = validate_utc_aware(absolute_deadline)
    if idle_deadline > absolute_deadline:
        raise encryption_error("idle_deadline must not exceed absolute_deadline")

    aad = _associated_data(
        schema_version=PROFILE_SESSION_SCHEMA_VERSION,
        profile_id=profile_id,
        session_id=session_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        login_binding=login_binding,
        sign_in=sign_in,
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
        login_binding=login_binding,
        sign_in=sign_in,
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
        raise encryption_error(f"session_key must be exactly {PROFILE_SESSION_KEY_BYTES} bytes")
    aad = _associated_data(
        schema_version=record.schema_version,
        profile_id=record.profile_id,
        session_id=record.session_id,
        custody_generation=record.custody_generation,
        dek_epoch=record.dek_epoch,
        login_binding=record.login_binding,
        sign_in=record.sign_in,
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


__all__ = [
    "PROFILE_SESSION_KEY_BYTES",
    "PROFILE_SESSION_LOGIN_ID_MAX_LENGTH",
    "PROFILE_SESSION_SCHEMA_VERSION",
    "LoginBindingDigest",
    "PersistedProfileSession",
    "profile_session_login_binding",
    "profile_session_login_matches",
    "unwrap_profile_session_dek",
    "validate_profile_session_metadata",
    "wrap_profile_session_dek",
]
