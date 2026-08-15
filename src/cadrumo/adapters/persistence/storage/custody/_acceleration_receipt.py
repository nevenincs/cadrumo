"""Profile acceleration receipt: cross-process custody of a wrapped bucket DEK.

This is NOT a session. It has no counterparty and no protocol: it is a
locally held wrap of an already-unlocked DEK, carrying a deadline, that lets a
later process skip the passphrase. The AEAT authority session -- an encrypted
row inside the bucket, revocable only with the key -- is the artefact that
owns the word "session" in this codebase, and conflating the two has produced
a wrong architectural premise more than once.

The "logged in" state minted by ``aeat config login`` survives across CLI
processes as two split-knowledge artefacts, either of which is useless
alone:

- an ephemeral 32-byte session key held ONLY in the OS keychain under the
  service ``cadrumo:profile-session:v2`` with the immutable profile UUID plus
  minted session UUID as account, and
- an on-disk ``session.v2.json`` record in the separated profile keystore
  directory carrying the AES-256-GCM wrap of the bucket DEK under that
  session key, with EVERY metadata field (schema version, immutable profile
  UUID, random session UUID,
  custody generation, DEK epoch, ``issued_at``, the sliding idle deadline,
  and immutable absolute deadline) bound as AEAD associated data.

A disk-only attacker sees ciphertext no more revealing than the
already-persisted wrapped ``bucket.dek.json``; a keychain-only attacker
holds a random key with nothing to decrypt; altering any persisted
deadline breaks the GCM tag. Resume evaluation is FAIL-CLOSED: an
expired, tampered, version-mismatched, or keychain-orphaned record is
deleted and refused with a typed
:class:`~cadrumo.core.ProfileSessionRefusalReason`, never silently
tolerated. No plaintext KEK, DEK, or session-key byte ever lands on disk.

Zeroisation honesty: the session key and DEK are held in ``bytearray``
buffers wiped through :func:`~adapters.persistence.storage.custody._zeroise.zeroise`
on every exit path, but the AEAD primitives and the pydantic boundary
require transient immutable ``bytes`` views whose lifetime the garbage
collector owns — the same best-effort contract
:class:`BucketSession` documents for the live in-process buffers.

Keychain failures are normalised to :class:`KeyringUnavailableError` on every
path, including failures raised OUTSIDE the ``keyring`` library's own
exception hierarchy. A backend can pass the class-level usability probe and
still fail at call time: the Windows credential store raises
``win32ctypes.pywin32.pywintypes.error`` (for example ``WinError 1312``, "a
specified logon session does not exist") from a process whose logon session
the credential manager cannot reach, and that type derives directly from
``Exception`` -- it is neither a ``KeyringError`` nor an ``OSError``, so a
guard naming either lets it escape as a raw traceback. Normalising here is
what makes the documented degradation reachable: no persisted artefact, a
process-scoped login, and a warning to the operator. The error type is caught
structurally rather than imported by name so this module carries no
platform-specific import.

See Also:
    :class:`~adapters.persistence.storage.master_key.BucketSession`
        The in-process materialisation this persisted record re-opens.
"""

from __future__ import annotations

import binascii
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import ProfileSessionRefusalReason
from .....core.base64_codec import b64_decode, b64_encode
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import (
    canonical_json_bytes,
    reject_duplicate_json_members,
    reject_json_constant,
)
from .....core.logging import get_logger
from .....core.time import validate_utc_aware
from .._storage_path_definitions import PROFILE_SESSION_FILENAME, PROFILE_SESSION_RETIREMENT_FILENAME
from ..crypto import EncryptedBlob, decrypt_record, encrypt_record
from ..errors import (
    DecryptionError,
    EncryptionError,
    KeyringUnavailableError,
    StorageError,
    StorageValidationError,
)
from ._errors import ProfileCustodyRecordError
from ._filesystem import (
    compare_and_clear_profile_custody_local_record,
    compare_and_replace_profile_custody_local_record,
    ensure_profile_custody_local_directory,
    profile_custody_local_lock,
    read_optional_profile_custody_local_record,
)
from ._zeroise import zeroise as _zeroise

_log = get_logger(__name__)

PROFILE_SESSION_KEYCHAIN_SERVICE: Final[str] = "cadrumo:profile-session:v2"
"""OS-keychain service name for current profile acceleration-receipt keys.

The token deliberately lags the concept name. It addresses entries in the OS
credential store, OUTSIDE the storage root, so a rename orphans every existing
entry: deleting the storage root cannot reap them, and code that deleted under
the old token first would be exactly the migration path this project forbids.
Permanent credential residue on real machines is the worse outcome, so the
wire identifier stays fixed while the code name says what the artefact is.
"""

PROFILE_SESSION_SCHEMA_VERSION: Final[int] = 2
"""Current persisted-session record schema version.

A record carrying any other version is a revocable cache from another
build: resume deletes it and refuses so the operator re-logs-in. This is
the deliberate, documented exemption from persisted-format durability
enrollment — losing a session record costs one re-login, never data.
"""

_SESSION_KEY_BYTES: Final[int] = 32
_DEK_BYTES: Final[int] = 32
_NONCE_BYTES: Final[int] = 12
_TAG_BYTES: Final[int] = 16
_AAD_PREFIX: Final[str] = "cadrumo.profile-session.v2"
PROFILE_SESSION_RECORD_MAX_BYTES: Final[int] = 8 * 1024
"""Strict ceiling for one canonical ``session.v2.json`` receipt."""

_PROFILE_SESSION_RETIREMENT_MAX_BYTES: Final[int] = 24 * 1024
_PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION: Final[int] = 1

_STORAGE_DECRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_decryption"
_STORAGE_ENCRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_encryption"


def _encryption_error(message: str) -> EncryptionError:
    return EncryptionError(message, translated_message=_STORAGE_ENCRYPTION_MESSAGE_KEY)


class PersistedProfileSession(BaseModel):
    """Frozen session-wrapped-DEK record for one bucket's profile session.

    ``nonce`` / ``ciphertext`` / ``tag`` carry the AES-256-GCM wrap of the
    32-byte bucket DEK under the keychain-held session key; every other
    field is bound into the AEAD associated data, so no metadata field can
    change without failing tag verification at
    :func:`unwrap_profile_session_dek`.
    """

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
    ciphertext: bytes = Field(min_length=_DEK_BYTES, max_length=_DEK_BYTES)
    tag: bytes = Field(min_length=_TAG_BYTES, max_length=_TAG_BYTES)

    @field_validator("issued_at", "idle_deadline", "absolute_deadline")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        """Reject naive or non-UTC deadlines at the model boundary."""
        return validate_utc_aware(value)


class _AccelerationReceiptDocument(BaseModel):
    """On-disk JSON envelope for one persisted profile session."""

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID
    custody_generation: int = Field(ge=1)
    dek_epoch: str = Field(min_length=1, max_length=128)
    issued_at: str = Field(min_length=1)
    idle_deadline: str = Field(min_length=1)
    absolute_deadline: str = Field(min_length=1)
    nonce_b64: str = Field(min_length=1)
    ciphertext_b64: str = Field(min_length=1)
    tag_b64: str = Field(min_length=1)


class _PendingReceiptRetirementDocument(BaseModel):
    """Bounded exact-byte receipt for an interrupted session-key rotation.

    ``predecessor_b64`` is absent only for the first mint.  Keeping both
    canonical receipt byte strings makes recovery an equality decision, not a
    reconstruction from mutable metadata: if the current receipt is the
    predecessor the staged successor is retired; if it is the successor the
    predecessor is retired.  Any third receipt is a concurrent substitution
    and is preserved/refused.
    """

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    profile_id: UUID
    predecessor_b64: str | None = None
    successor_b64: str = Field(min_length=1)


class ProfileSessionResumeOutcome(BaseModel):
    """Typed outcome of a fail-closed persisted-session resume evaluation.

    Never carries key material: the resumed DEK travels beside this record
    as a separate return value so no pydantic dump can surface it.
    """

    model_config = _STRICT_FROZEN

    resumed: bool
    refusal: ProfileSessionRefusalReason | None = None
    record: PersistedProfileSession | None = None


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
    """Compose the canonical AEAD associated data for one session record.

    Canonical JSON (sorted keys, no whitespace) keeps the composition
    unambiguous for every UUID-bound receipt, so no metadata value can be
    smuggled across a field boundary.
    """
    payload = canonical_json_bytes(
        {
            "absolute_deadline": absolute_deadline.isoformat(),
            "custody_generation": custody_generation,
            "dek_epoch": dek_epoch,
            "idle_deadline": idle_deadline.isoformat(),
            "issued_at": issued_at.isoformat(),
            "profile_id": str(profile_id),
            "schema_version": schema_version,
            "session_id": str(session_id),
        },
    )
    return f"{_AAD_PREFIX}:".encode(_UTF_8_ENCODING) + payload


# Wraps the bucket DEK under an ephemeral OS-keychain session key, for
# login-resumption custody. This is now the only wrap of the bucket DEK
# outside the profile's own password envelope: the sibling KEK-wrap that
# once carried it into a keystore sidecar was retired with that route.
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
    """Wrap ``dek`` under ``session_key`` with all metadata bound as AAD.

    Args:
        session_key: 32-byte ephemeral session key (keychain-held).
        dek: 32-byte bucket data-encryption key to wrap.
        profile_id: Immutable current-capsule profile UUID bound into AAD.
        session_id: Fresh random UUID naming this acceleration receipt.
        custody_generation: Current password-envelope generation.
        dek_epoch: Current immutable envelope DEK epoch.
        issued_at: UTC login instant.
        idle_deadline: UTC sliding idle deadline; must not exceed
            ``absolute_deadline``.
        absolute_deadline: UTC immutable session cap.

    Returns:
        A frozen :class:`PersistedProfileSession` carrying the wrap.

    Raises:
        EncryptionError: On a wrong-length key, invalid custody metadata, a
            non-UTC deadline, or an idle deadline past the absolute cap.
    """
    if len(session_key) != _SESSION_KEY_BYTES:
        raise _encryption_error(f"session_key must be exactly {_SESSION_KEY_BYTES} bytes")
    if len(dek) != _DEK_BYTES:
        raise _encryption_error(f"dek must be exactly {_DEK_BYTES} bytes")
    if custody_generation < 1:
        raise _encryption_error("custody_generation must be a strict positive integer")
    if not dek_epoch:
        raise _encryption_error("dek_epoch must be non-empty")
    issued_at = validate_utc_aware(issued_at)
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
    # Routes through the canonical AEAD primitives rather than calling
    # AESGCM directly. encrypt_record mints its own fresh nonce internally,
    # and EncryptedBlob.ciphertext (the cryptography library's
    # ciphertext-with-tag) is split into
    # PersistedProfileSession.ciphertext/.tag at the 32-byte boundary, so
    # the persisted PersistedProfileSession/_AccelerationReceiptDocument
    # shapes do not change.
    try:
        blob = encrypt_record(dek, key=session_key, associated_data=aad)
    except EncryptionError as exc:
        # Re-raise the SAME exception object (preserving its __cause__ chain)
        # with this module's translated_message, rather than wrapping it in a
        # new EncryptionError -- a caller inspecting __cause__ sees the real
        # underlying failure either way. Unreachable in practice: the
        # session_key/dek length checks above already refuse before this
        # call, but it is kept as defence in depth.
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
        ciphertext=blob.ciphertext[:_DEK_BYTES],
        tag=blob.ciphertext[_DEK_BYTES:],
    )


def unwrap_profile_session_dek(*, session_key: bytes, record: PersistedProfileSession) -> bytearray:
    """Recover the 32-byte DEK from ``record`` under ``session_key``.

    The AAD is recomputed from the record's own metadata fields, so any
    single-field mutation (a deadline extension, a bucket swap, a version
    edit) fails tag verification here.

    Args:
        session_key: 32-byte keychain-held session key.
        record: The persisted session record to unwrap.

    Returns:
        The 32-byte bucket data-encryption key, in a mutable buffer the caller
        can wipe. Handing it back as immutable ``bytes`` put it permanently
        beyond ``zeroise``, which refuses what it cannot overwrite in place --
        and a caller who copied it into a ``bytearray`` to wipe it was left
        with the original still resident and unreachable.

        One immutable copy is irreducible and is NOT wiped by this: the AEAD
        library returns plaintext as ``bytes``. What the caller receives is
        wipeable; the library's transient copy is a floor this cannot raise.

    Raises:
        EncryptionError: When ``session_key`` has the wrong length.
        DecryptionError: When AEAD tag verification fails.
    """
    if len(session_key) != _SESSION_KEY_BYTES:
        raise _encryption_error(f"session_key must be exactly {_SESSION_KEY_BYTES} bytes")
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
        # Same re-raise-in-place rationale as wrap_profile_session_dek:
        # preserves __cause__ (e.g. the underlying
        # cryptography.exceptions.InvalidTag) exactly.
        exc.translated_message = _STORAGE_DECRYPTION_MESSAGE_KEY
        raise


def advance_profile_session_idle_deadline(
    *,
    record: PersistedProfileSession,
    session_key: bytes,
    new_idle_deadline: datetime,
) -> PersistedProfileSession:
    """Return a re-wrapped record whose idle deadline advanced to ``new_idle_deadline``.

    The new deadline is clamped to the record's immutable absolute
    deadline; the DEK is unwrapped and re-wrapped under the same session
    key with a fresh nonce because the deadline participates in the AAD.
    The transient DEK buffer is zeroised before returning.

    Args:
        record: The currently-valid persisted session record.
        session_key: The record's keychain-held session key.
        new_idle_deadline: UTC instant the sliding window advances to.

    Returns:
        A new :class:`PersistedProfileSession` with the advanced deadline.

    Raises:
        DecryptionError: When the record fails tag verification.
        EncryptionError: When re-wrapping fails.
    """
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


class _ProfileSessionKeyring(Protocol):
    """Direct subset of the OS keychain used by session acceleration."""

    def set_password(self, service_name: str, username: str, password: str) -> None:
        """Persist one secret under the immutable account."""
        ...

    def get_password(self, service_name: str, username: str) -> str | None:
        """Load one exact secret, or return no entry."""
        ...

    def delete_password(self, service_name: str, username: str) -> None:
        """Remove one exact secret."""
        ...


def _keyring() -> tuple[_ProfileSessionKeyring, type[BaseException], type[BaseException]]:
    """Return the direct OS-keychain capability without master/provider reuse."""
    try:
        import keyring
        from keyring.errors import KeyringError, PasswordDeleteError
    except ImportError as exc:
        raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
    try:
        priority = float(getattr(keyring.get_keyring(), "priority", 0))
    except Exception as exc:
        raise KeyringUnavailableError(f"OS keychain cannot be inspected: {exc}") from exc
    if priority <= 0:
        raise KeyringUnavailableError("no usable OS keychain is configured for profile-session acceleration")
    return cast(_ProfileSessionKeyring, keyring), KeyringError, PasswordDeleteError


def _keychain_account(*, profile_id: UUID, session_id: UUID) -> str:
    """Return the immutable UUID-pair account for one acceleration receipt."""
    return f"{profile_id}:{session_id}"


def _store_acceleration_secret(*, profile_id: UUID, session_id: UUID, session_key: bytes) -> None:
    """Store and round-trip verify one fresh session key under its UUID pair."""
    if len(session_key) != _SESSION_KEY_BYTES:
        raise StorageValidationError(f"session_key must be exactly {_SESSION_KEY_BYTES} bytes")
    keyring, keyring_error, _password_delete_error = _keyring()
    account = _keychain_account(profile_id=profile_id, session_id=session_id)
    encoded = b64_encode(session_key)
    try:
        keyring.set_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account, encoded)
        roundtrip = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except keyring_error as exc:
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key write: {exc}") from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly on the profile-session key write: {exc}",
        ) from exc
    if roundtrip != encoded:
        _delete_acceleration_secret(profile_id=profile_id, session_id=session_id, suppress_unavailable=True)
        raise KeyringUnavailableError("OS keychain accepted the session key but its round-trip read disagreed")


def _load_acceleration_secret(*, profile_id: UUID, session_id: UUID) -> bytes | None:
    """Load one receipt's session key; malformed entries are cache-only cleanup."""
    keyring, keyring_error, _password_delete_error = _keyring()
    account = _keychain_account(profile_id=profile_id, session_id=session_id)
    try:
        stored = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except keyring_error as exc:
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key read: {exc}") from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly on the profile-session key read: {exc}",
        ) from exc
    if stored is None:
        return None
    try:
        key = b64_decode(stored)
    except (ValueError, binascii.Error):
        _delete_acceleration_secret(profile_id=profile_id, session_id=session_id, suppress_unavailable=False)
        return None
    if len(key) != _SESSION_KEY_BYTES:
        _delete_acceleration_secret(profile_id=profile_id, session_id=session_id, suppress_unavailable=False)
        return None
    return key


def _delete_acceleration_secret(
    *,
    profile_id: UUID,
    session_id: UUID,
    suppress_unavailable: bool,
) -> None:
    """Prove one known UUID-pair acceleration entry is absent.

    A missing account is an idempotent success.  A ``PasswordDeleteError``
    alone is not evidence that the backend is unavailable: a sibling may have
    retired this exact account after our first read.  Read once more and
    accept only an observed absence; otherwise preserve the calling journal
    under the typed unavailable path.
    """
    try:
        keyring, keyring_error, password_delete_error = _keyring()
        account = _keychain_account(profile_id=profile_id, session_id=session_id)
        try:
            present = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
        except keyring_error as exc:
            raise KeyringUnavailableError(
                f"OS keychain refused the profile-session key read before deletion: {exc}",
            ) from exc
        except Exception as exc:
            raise KeyringUnavailableError(
                f"OS keychain raised unexpectedly before profile-session key deletion: {exc}",
            ) from exc
        if present is None:
            return
        try:
            keyring.delete_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
        except password_delete_error:
            # A concurrent owner may have deleted it after ``present``.  Do
            # not turn that idempotent absence into a false unavailable
            # outcome; only a second exact read decides it.
            try:
                if keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account) is None:
                    return
            except keyring_error as exc:
                raise KeyringUnavailableError(
                    f"OS keychain refused the profile-session key deletion confirmation: {exc}",
                ) from exc
            except Exception as exc:
                raise KeyringUnavailableError(
                    f"OS keychain raised unexpectedly during profile-session key deletion confirmation: {exc}",
                ) from exc
            raise KeyringUnavailableError("OS keychain did not confirm profile-session key deletion") from None
        except keyring_error as exc:
            raise KeyringUnavailableError(f"OS keychain refused the profile-session key deletion: {exc}") from exc
        except Exception as exc:
            raise KeyringUnavailableError(
                f"OS keychain raised unexpectedly during profile-session key deletion: {exc}",
            ) from exc
        try:
            absent = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account) is None
        except keyring_error as exc:
            raise KeyringUnavailableError(
                f"OS keychain refused the profile-session key deletion confirmation: {exc}",
            ) from exc
        except Exception as exc:
            raise KeyringUnavailableError(
                f"OS keychain raised unexpectedly during profile-session key deletion confirmation: {exc}",
            ) from exc
        if not absent:
            raise KeyringUnavailableError("OS keychain did not confirm profile-session key deletion")
    except Exception as exc:
        if suppress_unavailable:
            _log.debug("profile-session key cleanup deferred error_type=%s", type(exc).__name__)
            return
        if isinstance(exc, KeyringUnavailableError):
            raise
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key deletion: {exc}") from exc


def profile_session_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return the locator consumed exclusively by custody local-record operations."""
    from ..bucket import keystore_sidecar_path

    return keystore_sidecar_path(
        storage_root=storage_root,
        bucket_id=str(profile_id),
        filename=PROFILE_SESSION_FILENAME,
    )


def _profile_session_retirement_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return the bounded local receipt for one interrupted session-key swap."""
    return profile_session_path(storage_root=storage_root, profile_id=profile_id).with_name(
        PROFILE_SESSION_RETIREMENT_FILENAME,
    )


def _profile_session_lock_path(receipt_path: Path) -> Path:
    """Return the separate anchored lock leaf; never lock the receipt itself."""
    return receipt_path.with_name(f".{receipt_path.name}.lock")


def _ensure_profile_session_directory(path: Path) -> None:
    """Provision only the two custody-owned keystore children, anchored.

    The configured storage root itself is an existing product boundary.  The
    session sidecar owns the ``keystore`` child and then its UUID child; using
    the custody primitive for both avoids a recursive convenience mkdir walk.
    """
    ensure_profile_custody_local_directory(path.parent.parent)
    ensure_profile_custody_local_directory(path.parent)


def _document_from_record(record: PersistedProfileSession) -> _AccelerationReceiptDocument:
    return _AccelerationReceiptDocument(
        schema_version=record.schema_version,
        profile_id=record.profile_id,
        session_id=record.session_id,
        custody_generation=record.custody_generation,
        dek_epoch=record.dek_epoch,
        issued_at=record.issued_at.isoformat(),
        idle_deadline=record.idle_deadline.isoformat(),
        absolute_deadline=record.absolute_deadline.isoformat(),
        nonce_b64=b64_encode(record.nonce),
        ciphertext_b64=b64_encode(record.ciphertext),
        tag_b64=b64_encode(record.tag),
    )


def _record_from_document(document: _AccelerationReceiptDocument) -> PersistedProfileSession:
    """Hydrate the strict record from an on-disk document.

    Raises:
        ValueError: On any malformed field (base64, datetime, enum, or
            length); the resume evaluation maps this to the ``MALFORMED``
            refusal.
    """
    return PersistedProfileSession(
        schema_version=document.schema_version,
        profile_id=document.profile_id,
        session_id=document.session_id,
        custody_generation=document.custody_generation,
        dek_epoch=document.dek_epoch,
        issued_at=validate_utc_aware(datetime.fromisoformat(document.issued_at)),
        idle_deadline=validate_utc_aware(datetime.fromisoformat(document.idle_deadline)),
        absolute_deadline=validate_utc_aware(datetime.fromisoformat(document.absolute_deadline)),
        nonce=b64_decode(document.nonce_b64),
        ciphertext=b64_decode(document.ciphertext_b64),
        tag=b64_decode(document.tag_b64),
    )


def _canonical_document_bytes(document: BaseModel) -> bytes:
    """Encode one strict receipt with the sole accepted JSON byte spelling."""
    return canonical_json_bytes(document.model_dump(mode="json"))


def _parse_canonical_document(payload: bytes, model: type[BaseModel]) -> BaseModel:
    """Decode exact canonical JSON without accepting duplicate-key aliases."""
    decoded = payload.decode(_UTF_8_ENCODING)
    parsed = json.loads(
        decoded,
        object_pairs_hook=reject_duplicate_json_members,
        parse_constant=reject_json_constant,
    )
    if not isinstance(parsed, dict):
        raise ValueError("session receipt must be a JSON object")
    # ``strict`` models deliberately accept their wire UUID/datetime strings
    # only through Pydantic's JSON boundary.  The independent ``json.loads``
    # above owns duplicate/non-finite refusal before this typed decode.
    document = model.model_validate_json(payload)
    if _canonical_document_bytes(document) != payload:
        raise ValueError("session receipt bytes are not canonical")
    return document


def _receipt_bytes(record: PersistedProfileSession) -> bytes:
    return _canonical_document_bytes(_document_from_record(record))


def _record_from_canonical_receipt(payload: bytes) -> PersistedProfileSession:
    document = cast(_AccelerationReceiptDocument, _parse_canonical_document(payload, _AccelerationReceiptDocument))
    return _record_from_document(document)


def _read_receipt(path: Path) -> tuple[bytes, PersistedProfileSession] | None:
    """Read and parse one receipt through the canonical anchored authority."""
    payload = read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
    if payload is None:
        return None
    return payload, _record_from_canonical_receipt(payload)


def _clear_captured_receipt(path: Path, *, payload: bytes, maximum_bytes: int) -> bool:
    """Clear only the exact anchored bytes already evaluated by this caller."""
    try:
        compare_and_clear_profile_custody_local_record(
            path,
            expected=payload,
            maximum_bytes=maximum_bytes,
        )
    except ProfileCustodyRecordError:
        return False
    return True


def _write_acceleration_receipt(
    *,
    storage_root: Path,
    profile_id: UUID,
    record: PersistedProfileSession,
    predecessor: bytes | None,
) -> bytes:
    """CAS-publish a canonical receipt through the custody local-record owner."""
    if record.profile_id != profile_id:
        raise StorageValidationError(
            f"session record profile {record.profile_id!s} does not match target profile {profile_id!s}",
        )
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    payload = _receipt_bytes(record)
    _ensure_profile_session_directory(path)
    compare_and_replace_profile_custody_local_record(
        path,
        expected=predecessor,
        replacement=payload,
        maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
    )
    return payload


def _pending_retirement_bytes(*, profile_id: UUID, predecessor: bytes | None, successor: bytes) -> bytes:
    """Encode the bounded exact-byte retirement decision before publication."""
    return _canonical_document_bytes(
        _PendingReceiptRetirementDocument(
            schema_version=_PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION,
            profile_id=profile_id,
            predecessor_b64=None if predecessor is None else b64_encode(predecessor),
            successor_b64=b64_encode(successor),
        ),
    )


def _read_pending_retirement(path: Path, *, profile_id: UUID) -> tuple[bytes, bytes | None, bytes] | None:
    """Load a current pending-swap receipt, rejecting aliases before action."""
    payload = read_optional_profile_custody_local_record(path, maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES)
    if payload is None:
        return None
    document = cast(
        _PendingReceiptRetirementDocument,
        _parse_canonical_document(payload, _PendingReceiptRetirementDocument),
    )
    if document.schema_version != _PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION:
        raise StorageValidationError("profile-session retirement receipt schema is not current")
    if document.profile_id != profile_id:
        raise StorageValidationError("profile-session retirement receipt profile differs")
    predecessor = None if document.predecessor_b64 is None else b64_decode(document.predecessor_b64)
    successor = b64_decode(document.successor_b64)
    if predecessor is not None:
        prior_record = _record_from_canonical_receipt(predecessor)
        if prior_record.profile_id != profile_id:
            raise StorageValidationError("profile-session retirement predecessor profile differs")
    successor_record = _record_from_canonical_receipt(successor)
    if successor_record.profile_id != profile_id:
        raise StorageValidationError("profile-session retirement successor profile differs")
    return payload, predecessor, successor


def _recover_pending_retirement(*, storage_root: Path, profile_id: UUID) -> bool:
    """Finish exactly one interrupted ordered session-key swap.

    Returns ``True`` only when there was no journal or the exact journal was
    consumed.  It never clears a receipt whose bytes differ from the recorded
    predecessor/successor pair.
    """
    receipt_path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    journal_path = _profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    pending = _read_pending_retirement(journal_path, profile_id=profile_id)
    if pending is None:
        return True
    journal_payload, predecessor, successor = pending
    current = read_optional_profile_custody_local_record(
        receipt_path,
        maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
    )
    if current == successor:
        if predecessor is not None:
            prior = _record_from_canonical_receipt(predecessor)
            _delete_acceleration_secret(
                profile_id=prior.profile_id,
                session_id=prior.session_id,
                suppress_unavailable=False,
            )
        if not _clear_captured_receipt(
            journal_path,
            payload=journal_payload,
            maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
        ):
            raise StorageValidationError("profile-session retirement receipt changed during recovery")
        return True
    if current == predecessor:
        successor_record = _record_from_canonical_receipt(successor)
        _delete_acceleration_secret(
            profile_id=successor_record.profile_id,
            session_id=successor_record.session_id,
            suppress_unavailable=False,
        )
        if not _clear_captured_receipt(
            journal_path,
            payload=journal_payload,
            maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
        ):
            raise StorageValidationError("profile-session retirement receipt changed during rollback")
        return True
    raise StorageValidationError("profile-session retirement receipt conflicts with the current receipt")


def _discard_known_record(*, path: Path, payload: bytes, record: PersistedProfileSession) -> bool:
    """Revoke one verified cache entry, then clear the exact captured receipt."""
    try:
        _delete_acceleration_secret(
            profile_id=record.profile_id,
            session_id=record.session_id,
            suppress_unavailable=False,
        )
    except KeyringUnavailableError:
        return False
    return _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)


class AccelerationReceiptRevocationError(StorageError):
    """Raised when a receipt survived the revocation that was asked to remove it.

    Deliberately NOT a subclass of the custody record error this module already
    catches and logs, because the point is that it must not be swallowed by the
    same handler.

    A boolean return would have repeated the defect one level up: the caller
    that ignored the value is precisely the caller that reports the profile
    closed. The revocation entry point is the single authority for "this
    profile is no longer logged in", so when it cannot prove the receipt is
    gone it must not return as though it had.
    """


def delete_profile_session(*, storage_root: Path, profile_id: UUID) -> None:
    """Revoke only receipts whose exact bytes/name were safely observed.

    Raises:
        AccelerationReceiptRevocationError: The compare-and-clear refused, so
            the receipt is still on disk. Reached whenever the clear cannot
            remove the file -- an open handle on Windows is the ordinary case,
            not only a byte substitution racing the lock -- and previously this
            returned silently while the receipt survived.
    """
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    try:
        _ensure_profile_session_directory(path)
        with profile_custody_local_lock(_profile_session_lock_path(path)):
            try:
                _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
            except (KeyringUnavailableError, ProfileCustodyRecordError, StorageValidationError) as exc:
                _log.debug("profile-session retirement recovery deferred error_type=%s", type(exc).__name__)
            try:
                observed = _read_receipt(path)
            except (ProfileCustodyRecordError, ValueError, ValidationError) as exc:
                _log.debug("profile-session receipt cannot be decoded for deletion error_type=%s", type(exc).__name__)
                return
            if observed is None:
                return
            payload, record = observed
            if record.profile_id == profile_id:
                _delete_acceleration_secret(
                    profile_id=record.profile_id,
                    session_id=record.session_id,
                    suppress_unavailable=True,
                )
            if not _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES):
                raise AccelerationReceiptRevocationError(
                    translated_message="errors.fail.fail_acceleration_receipt_revocation",
                    context={"profile_id": str(profile_id)},
                )
    except ProfileCustodyRecordError as exc:
        _log.debug("profile-session receipt deletion refused error_type=%s", type(exc).__name__)


def mint_profile_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    dek: bytes,
    now: datetime,
    idle_minutes: int,
    absolute_minutes: int,
) -> PersistedProfileSession:
    """Mint the persisted session for a freshly-authenticated login.

    Generates the ephemeral session key, wraps ``dek`` under it with the
    deadline metadata AAD-bound, stores the key in the OS keychain
    (round-trip verified), and atomically writes the on-disk record. The
    session-key buffer is zeroised on every exit path. On a host with no
    usable keychain the mint REFUSES before writing anything, so no
    artefact can exist whose key has no secure home.

    Args:
        storage_root: The Cadrumo storage root owning the profile keystore.
        profile_id: Immutable authenticated capsule UUID.
        custody_generation: Current envelope generation.
        dek_epoch: Current envelope DEK epoch.
        dek: The unwrapped 32-byte bucket DEK to session-wrap.
        now: UTC login instant (becomes ``issued_at``).
        idle_minutes: Sliding idle window; strict positive.
        absolute_minutes: Immutable absolute cap; strict positive.

    Returns:
        The persisted :class:`PersistedProfileSession`.

    Raises:
        StorageValidationError: On non-positive windows.
        EncryptionError: On wrap failure.
        KeyringUnavailableError: When the OS keychain cannot custody the
            session key.
    """
    if idle_minutes <= 0:
        raise StorageValidationError("idle_minutes must be a strict positive integer")
    if absolute_minutes <= 0:
        raise StorageValidationError("absolute_minutes must be a strict positive integer")
    now = validate_utc_aware(now)
    absolute_deadline = now + timedelta(minutes=absolute_minutes)
    idle_deadline = min(now + timedelta(minutes=idle_minutes), absolute_deadline)

    receipt_path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    retirement_path = _profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    _ensure_profile_session_directory(receipt_path)
    with profile_custody_local_lock(_profile_session_lock_path(receipt_path)):
        # A prior crash or retirement failure has one bounded exact-byte
        # decision to finish before another random account can be minted.
        _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
        prior = _read_receipt(receipt_path)
        predecessor = None if prior is None else prior[0]

        session_key_buffer = bytearray(secrets.token_bytes(_SESSION_KEY_BYTES))
        session_id = uuid4()
        try:
            record = wrap_profile_session_dek(
                session_key=bytes(session_key_buffer),
                dek=dek,
                profile_id=profile_id,
                session_id=session_id,
                custody_generation=custody_generation,
                dek_epoch=dek_epoch,
                issued_at=now,
                idle_deadline=idle_deadline,
                absolute_deadline=absolute_deadline,
            )
            successor = _receipt_bytes(record)
            journal = _pending_retirement_bytes(
                profile_id=profile_id,
                predecessor=predecessor,
                successor=successor,
            )
            # Publish the deterministic cleanup instruction first.  If this
            # process dies before a later phase, recovery sees whether the
            # exact current receipt is predecessor or successor and retires
            # only the corresponding staged/displaced UUID-pair account.
            compare_and_replace_profile_custody_local_record(
                retirement_path,
                expected=None,
                replacement=journal,
                maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
            )
            try:
                _store_acceleration_secret(
                    profile_id=profile_id,
                    session_id=session_id,
                    session_key=bytes(session_key_buffer),
                )
                published = _write_acceleration_receipt(
                    storage_root=storage_root,
                    profile_id=profile_id,
                    record=record,
                    predecessor=predecessor,
                )
                verified = read_optional_profile_custody_local_record(
                    receipt_path,
                    maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
                )
                if verified != published:
                    raise StorageValidationError("profile-session receipt publication could not be verified")
            except BaseException:
                # Do not hand-delete an account whose publication state is
                # unknown.  The exact pending receipt is the recovery owner;
                # it will clean a pre-publication successor or finish
                # retirement after publication without touching a substitute.
                try:
                    _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
                except (KeyringUnavailableError, ProfileCustodyRecordError, StorageValidationError) as exc:
                    _log.debug("profile-session mint cleanup deferred error_type=%s", type(exc).__name__)
                raise
            try:
                _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
            except KeyringUnavailableError as exc:
                # The new receipt/key pair is already verified and remains a
                # valid acceleration.  Retiring its displaced predecessor is
                # explicitly retryable through the journal, never an
                # authentication failure or a global account sweep.
                _log.debug("profile-session predecessor retirement deferred error_type=%s", type(exc).__name__)
            return record
        finally:
            _zeroise(session_key_buffer)


def _refusal(
    reason: ProfileSessionRefusalReason,
    record: PersistedProfileSession | None = None,
) -> tuple[ProfileSessionResumeOutcome, None]:
    return ProfileSessionResumeOutcome(resumed=False, refusal=reason, record=record), None


def resume_profile_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Fail-closed evaluation of one current profile acceleration receipt.

    The recovered key is a WIPEABLE ``bytearray``, and the annotation says so:
    the caller owns it and is expected to zeroise it once the session holds its
    own copy. Declaring immutable ``bytes`` here would leave every caller typed
    to receive material it cannot wipe, which is what the unwrap was widened to
    avoid.

    Expired and tampered receipts are narrowly removed when the matching
    keychain entry is reachable.  If the OS keychain is unavailable, the
    receipt remains evidence and the typed ``KEYRING_UNAVAILABLE`` refusal
    leaves the login process-scoped:

    - absent record: refusal ``ABSENT`` (ordinary logged-out state, nothing
      to delete);
    - unreadable / strict-validation failure: delete both artefacts,
      ``MALFORMED``;
    - non-current ``schema_version`` or a record naming another bucket:
      delete both, ``SCHEMA_VERSION_MISMATCH`` / ``TAMPERED``;
    - elapsed absolute or idle deadline: delete both,
      ``EXPIRED_ABSOLUTE`` / ``EXPIRED_IDLE``;
    - missing keychain entry: delete the record, ``KEYCHAIN_ENTRY_MISSING``
      (logged-out treatment);
    - AEAD tag failure: delete both, ``TAMPERED``.

    Args:
        storage_root: The Cadrumo storage root owning the profile keystore.
        profile_id: Immutable capsule UUID expected by the live pointer.
        custody_generation: Current authenticated envelope generation.
        dek_epoch: Current authenticated envelope DEK epoch.
        now: UTC instant of the evaluation.

    Returns:
        A ``(outcome, dek)`` pair. ``dek`` is the unwrapped 32-byte bucket
        DEK when ``outcome.resumed`` is true and ``None`` otherwise; it is
        deliberately NOT carried on the outcome model so key material never
        rides a dumpable record.

    Raises:
        KeyringUnavailableError: When the keychain backend is unusable (the
            caller decides between refusal and the no-persistence path).
    """
    now = validate_utc_aware(now)
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    try:
        _ensure_profile_session_directory(path)
        with profile_custody_local_lock(_profile_session_lock_path(path)):
            # A predecessor cleanup failure is non-authoritative: attempt
            # deterministic convergence before using the successor, but do
            # not unlock through a substituted/ambiguous journal.
            try:
                _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
            except KeyringUnavailableError:
                observed = _read_receipt(path)
                return _refusal(
                    ProfileSessionRefusalReason.KEYRING_UNAVAILABLE,
                    None if observed is None else observed[1],
                )

            payload = read_optional_profile_custody_local_record(
                path,
                maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
            )
            if payload is None:
                return _refusal(ProfileSessionRefusalReason.ABSENT)
            try:
                record = _record_from_canonical_receipt(payload)
            except (ValueError, ValidationError):
                _log.debug("profile-session record malformed; refusing profile_id=%s", profile_id)
                _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
                return _refusal(ProfileSessionRefusalReason.MALFORMED)

            if record.schema_version != PROFILE_SESSION_SCHEMA_VERSION:
                if not _discard_known_record(path=path, payload=payload, record=record):
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
                return _refusal(ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH)
            if record.profile_id != profile_id:
                if not _discard_known_record(path=path, payload=payload, record=record):
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
                return _refusal(ProfileSessionRefusalReason.TAMPERED)
            if record.custody_generation != custody_generation or record.dek_epoch != dek_epoch:
                if not _discard_known_record(path=path, payload=payload, record=record):
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
                return _refusal(ProfileSessionRefusalReason.CUSTODY_CHANGED, record)
            if now >= record.absolute_deadline:
                if not _discard_known_record(path=path, payload=payload, record=record):
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
                return _refusal(ProfileSessionRefusalReason.EXPIRED_ABSOLUTE, record)
            if now >= record.idle_deadline:
                if not _discard_known_record(path=path, payload=payload, record=record):
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
                return _refusal(ProfileSessionRefusalReason.EXPIRED_IDLE, record)

            try:
                session_key = _load_acceleration_secret(profile_id=record.profile_id, session_id=record.session_id)
            except KeyringUnavailableError:
                return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
            if session_key is None:
                _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
                return _refusal(ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING, record)

            session_key_buffer = bytearray(session_key)
            del session_key
            try:
                dek = unwrap_profile_session_dek(session_key=bytes(session_key_buffer), record=record)
            except DecryptionError:
                if not _discard_known_record(path=path, payload=payload, record=record):
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, record)
                return _refusal(ProfileSessionRefusalReason.TAMPERED, record)
            finally:
                _zeroise(session_key_buffer)
            return ProfileSessionResumeOutcome(resumed=True, refusal=None, record=record), dek
    except (ProfileCustodyRecordError, StorageValidationError, ValueError, ValidationError) as exc:
        _log.debug("profile-session receipt access refused error_type=%s", type(exc).__name__)
        return _refusal(ProfileSessionRefusalReason.MALFORMED)


def advance_persisted_profile_session_idle_deadline(
    *,
    storage_root: Path,
    profile_id: UUID,
    record: PersistedProfileSession,
    new_idle_deadline: datetime,
) -> PersistedProfileSession:
    """Advance an already-resumed receipt without exposing its key upstream."""
    if record.profile_id != profile_id:
        raise StorageValidationError("persisted session record belongs to another profile")
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    _ensure_profile_session_directory(path)
    with profile_custody_local_lock(_profile_session_lock_path(path)):
        observed = _read_receipt(path)
        if observed is None:
            raise KeyringUnavailableError("profile-session receipt disappeared before idle renewal")
        predecessor, current = observed
        if current != record:
            raise StorageValidationError("profile-session receipt changed before idle renewal")
        session_key = _load_acceleration_secret(profile_id=record.profile_id, session_id=record.session_id)
        if session_key is None:
            raise KeyringUnavailableError("profile-session keychain entry disappeared before idle renewal")
        key_buffer = bytearray(session_key)
        try:
            advanced = advance_profile_session_idle_deadline(
                record=record,
                session_key=bytes(key_buffer),
                new_idle_deadline=new_idle_deadline,
            )
            _write_acceleration_receipt(
                storage_root=storage_root,
                profile_id=profile_id,
                record=advanced,
                predecessor=predecessor,
            )
            return advanced
        finally:
            _zeroise(key_buffer)


__all__ = [
    "PROFILE_SESSION_KEYCHAIN_SERVICE",
    "PROFILE_SESSION_SCHEMA_VERSION",
    "PersistedProfileSession",
    "ProfileSessionResumeOutcome",
    "advance_persisted_profile_session_idle_deadline",
    "advance_profile_session_idle_deadline",
    "delete_profile_session",
    "mint_profile_session",
    "profile_session_path",
    "resume_profile_session",
    "unwrap_profile_session_dek",
    "wrap_profile_session_dek",
]
