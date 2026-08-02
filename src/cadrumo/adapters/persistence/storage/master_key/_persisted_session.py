"""Persisted cross-process profile session: session-wrapped DEK custody.

The "logged in" state minted by ``aeat config login`` survives across CLI
processes as two split-knowledge artefacts, either of which is useless
alone:

- an ephemeral 32-byte session key held ONLY in the OS keychain under the
  service ``cadrumo:profile-session`` with the bucket UUID as account, and
- an on-disk ``session.v1.json`` record in the separated bucket keystore
  directory carrying the AES-256-GCM wrap of the bucket DEK under that
  session key, with EVERY metadata field (schema version, bucket id,
  backend kind, ``authenticated_at``, the sliding idle deadline, and the
  immutable absolute deadline) bound as AEAD associated data.

A disk-only attacker sees ciphertext no more revealing than the
already-persisted wrapped ``bucket.dek.json``; a keychain-only attacker
holds a random key with nothing to decrypt; altering any persisted
deadline breaks the GCM tag. Resume evaluation is FAIL-CLOSED: an
expired, tampered, version-mismatched, or keychain-orphaned record is
deleted and refused with a typed
:class:`~cadrumo.core.ProfileSessionRefusalReason`, never silently
tolerated. No plaintext KEK, DEK, or session-key byte ever lands on disk.

Zeroisation honesty: the session key and DEK are held in ``bytearray``
buffers wiped through :func:`~adapters.persistence.storage.master_key._zeroise.zeroise`
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
    :mod:`adapters.persistence.storage.master_key._dek_wrap`
        The sibling KEK-wrap of the same DEK (enrollment custody).
"""

from __future__ import annotations

import binascii
import contextlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field, ValidationError, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import ProfileSessionRefusalReason
from .....core.config import SecretStoreBackend
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.identity import BucketId
from .....core.logging import get_logger
from .....core.time import validate_utc_aware
from .._namespace_registry import PROFILE_SESSION_FILENAME
from ..errors import (
    DecryptionError,
    EncryptionError,
    KeyringUnavailableError,
    StorageValidationError,
)
from ._bucket_identity import canonical_bucket_id
from ._master_key import KeyringMasterKeyProvider as _KeyringMasterKeyProvider
from ._master_key_io import _b64decode, _b64encode, atomic_write_secure_bytes
from ._zeroise import zeroise as _zeroise

_log = get_logger(__name__)

PROFILE_SESSION_KEYCHAIN_SERVICE: Final[str] = "cadrumo:profile-session"
"""OS-keychain service name for per-bucket profile-session keys."""

PROFILE_SESSION_SCHEMA_VERSION: Final[int] = 1
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
_AAD_PREFIX: Final[str] = "cadrumo.profile-session.v1"

_STORAGE_DECRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_decryption"
_STORAGE_ENCRYPTION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_encryption"


def _encryption_error(message: str) -> EncryptionError:
    return EncryptionError(message, translated_message=_STORAGE_ENCRYPTION_MESSAGE_KEY)


def _decryption_error(message: str) -> DecryptionError:
    return DecryptionError(message, translated_message=_STORAGE_DECRYPTION_MESSAGE_KEY)


_NONCANONICAL_BUCKET_MESSAGE: Final[str] = "bucket_id must be a canonical bucket identity"


def _crypto_bucket_id(bucket_id: str) -> str:
    """Canonicalize a bucket identity for the AEAD-binding surfaces."""
    try:
        return canonical_bucket_id(bucket_id)
    except ValueError as exc:
        raise _encryption_error(_NONCANONICAL_BUCKET_MESSAGE) from exc


def _keychain_bucket_id(bucket_id: str) -> str:
    """Canonicalize a bucket identity used as an OS-keychain account name.

    The keychain account is the bucket id verbatim, so two spellings of one
    bucket addressed two different keychain entries: a session key stored
    under one spelling was invisible to a lookup under the other, and the
    split showed up as an unexplained resume failure rather than as the
    identity error it is.
    """
    try:
        return canonical_bucket_id(bucket_id)
    except ValueError as exc:
        raise StorageValidationError(_NONCANONICAL_BUCKET_MESSAGE) from exc


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
    bucket_id: BucketId
    backend_kind: SecretStoreBackend
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    nonce: bytes = Field(min_length=_NONCE_BYTES, max_length=_NONCE_BYTES)
    ciphertext: bytes = Field(min_length=_DEK_BYTES, max_length=_DEK_BYTES)
    tag: bytes = Field(min_length=_TAG_BYTES, max_length=_TAG_BYTES)

    @field_validator("authenticated_at", "idle_deadline", "absolute_deadline")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        """Reject naive or non-UTC deadlines at the model boundary."""
        return validate_utc_aware(value)


class _PersistedSessionDocument(BaseModel):
    """On-disk JSON envelope for one persisted profile session."""

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    bucket_id: BucketId
    backend_kind: str = Field(min_length=1)
    authenticated_at: str = Field(min_length=1)
    idle_deadline: str = Field(min_length=1)
    absolute_deadline: str = Field(min_length=1)
    nonce_b64: str = Field(min_length=1)
    ciphertext_b64: str = Field(min_length=1)
    tag_b64: str = Field(min_length=1)


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
    bucket_id: str,
    backend_kind: SecretStoreBackend,
    authenticated_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
) -> bytes:
    """Compose the canonical AEAD associated data for one session record.

    Canonical JSON (sorted keys, no whitespace) keeps the composition
    unambiguous for arbitrary bucket ids, so no metadata value can be
    smuggled across a field boundary.
    """
    payload = json.dumps(
        {
            "absolute_deadline": absolute_deadline.isoformat(),
            "authenticated_at": authenticated_at.isoformat(),
            "backend_kind": backend_kind.value,
            "bucket_id": bucket_id,
            "idle_deadline": idle_deadline.isoformat(),
            "schema_version": schema_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{_AAD_PREFIX}:{payload}".encode(_UTF_8_ENCODING)


def wrap_profile_session_dek(
    *,
    session_key: bytes,
    dek: bytes,
    bucket_id: str,
    backend_kind: SecretStoreBackend,
    authenticated_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
) -> PersistedProfileSession:
    """Wrap ``dek`` under ``session_key`` with all metadata bound as AAD.

    Args:
        session_key: 32-byte ephemeral session key (keychain-held).
        dek: 32-byte bucket data-encryption key to wrap.
        bucket_id: Non-empty bucket identifier bound into the AAD.
        backend_kind: The custody backend that authenticated the login.
        authenticated_at: UTC login instant.
        idle_deadline: UTC sliding idle deadline; must not exceed
            ``absolute_deadline``.
        absolute_deadline: UTC immutable session cap.

    Returns:
        A frozen :class:`PersistedProfileSession` carrying the wrap.

    Raises:
        EncryptionError: On a wrong-length key, a noncanonical bucket id, a
            non-UTC deadline, or an idle deadline past the absolute cap.
    """
    if len(session_key) != _SESSION_KEY_BYTES:
        raise _encryption_error(f"session_key must be exactly {_SESSION_KEY_BYTES} bytes")
    if len(dek) != _DEK_BYTES:
        raise _encryption_error(f"dek must be exactly {_DEK_BYTES} bytes")
    # Canonicalize BEFORE composing the AAD, not merely before storing.
    # The record's own field is normalized by its BucketId type, and unwrap
    # recomputes the AAD from that stored field -- so binding the caller's
    # raw spelling here would make a whitespace-wrapped id produce a record
    # that could never be unwrapped at all.
    bucket_id = _crypto_bucket_id(bucket_id)
    authenticated_at = validate_utc_aware(authenticated_at)
    idle_deadline = validate_utc_aware(idle_deadline)
    absolute_deadline = validate_utc_aware(absolute_deadline)
    if idle_deadline > absolute_deadline:
        raise _encryption_error("idle_deadline must not exceed absolute_deadline")

    nonce = secrets.token_bytes(_NONCE_BYTES)
    aad = _associated_data(
        schema_version=PROFILE_SESSION_SCHEMA_VERSION,
        bucket_id=bucket_id,
        backend_kind=backend_kind,
        authenticated_at=authenticated_at,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
    )
    try:
        cipher_with_tag = AESGCM(session_key).encrypt(nonce, dek, aad)
    except (TypeError, ValueError) as exc:
        raise _encryption_error("profile-session DEK wrap failed") from exc
    return PersistedProfileSession(
        schema_version=PROFILE_SESSION_SCHEMA_VERSION,
        bucket_id=bucket_id,
        backend_kind=backend_kind,
        authenticated_at=authenticated_at,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
        nonce=nonce,
        ciphertext=cipher_with_tag[:_DEK_BYTES],
        tag=cipher_with_tag[_DEK_BYTES:],
    )


def unwrap_profile_session_dek(*, session_key: bytes, record: PersistedProfileSession) -> bytes:
    """Recover the 32-byte DEK from ``record`` under ``session_key``.

    The AAD is recomputed from the record's own metadata fields, so any
    single-field mutation (a deadline extension, a bucket swap, a version
    edit) fails tag verification here.

    Args:
        session_key: 32-byte keychain-held session key.
        record: The persisted session record to unwrap.

    Returns:
        The 32-byte bucket data-encryption key.

    Raises:
        EncryptionError: When ``session_key`` has the wrong length.
        DecryptionError: When AEAD tag verification fails.
    """
    if len(session_key) != _SESSION_KEY_BYTES:
        raise _encryption_error(f"session_key must be exactly {_SESSION_KEY_BYTES} bytes")
    aad = _associated_data(
        schema_version=record.schema_version,
        bucket_id=record.bucket_id,
        backend_kind=record.backend_kind,
        authenticated_at=record.authenticated_at,
        idle_deadline=record.idle_deadline,
        absolute_deadline=record.absolute_deadline,
    )
    try:
        return AESGCM(session_key).decrypt(record.nonce, record.ciphertext + record.tag, aad)
    except InvalidTag as exc:
        raise _decryption_error("profile-session DEK unwrap tag verification failed") from exc
    except (TypeError, ValueError) as exc:
        raise _decryption_error("profile-session DEK unwrap failed") from exc


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
    dek_buffer = bytearray(unwrap_profile_session_dek(session_key=session_key, record=record))
    try:
        return wrap_profile_session_dek(
            session_key=session_key,
            dek=bytes(dek_buffer),
            bucket_id=record.bucket_id,
            backend_kind=record.backend_kind,
            authenticated_at=record.authenticated_at,
            idle_deadline=clamped,
            absolute_deadline=record.absolute_deadline,
        )
    finally:
        _zeroise(dek_buffer)


def _probe_keychain_backend() -> None:
    """Refuse no-op keychain backends before any session-key custody call.

    Delegates to the same probe the keyring master-key provider runs so a
    ``fail.Keyring`` / ``null.Keyring`` host can never mint a persisted
    session whose key silently evaporated.

    Raises:
        KeyringUnavailableError: When no usable OS keychain backend exists.
    """
    _KeyringMasterKeyProvider()._probe_backend()


def store_profile_session_key(*, bucket_id: str, session_key: bytes) -> None:
    """Persist ``session_key`` in the OS keychain for ``bucket_id``.

    The write is round-trip verified so a silently-dropping backend is
    detected before the on-disk record is written; on verification failure
    the entry is best-effort deleted and the store refuses.

    Args:
        bucket_id: Bucket identifier, canonicalized to form the keychain
            account so two spellings cannot address two entries.
        session_key: 32-byte session key to custody.

    Raises:
        StorageValidationError: When ``bucket_id`` is not a canonical bucket
            identity or the key has the wrong length.
        KeyringUnavailableError: When the keychain is unusable, refuses the
            write, or fails the round-trip verification.
    """
    bucket_id = _keychain_bucket_id(bucket_id)
    if len(session_key) != _SESSION_KEY_BYTES:
        raise StorageValidationError(f"session_key must be exactly {_SESSION_KEY_BYTES} bytes")
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError as exc:
        raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
    _probe_keychain_backend()
    encoded = _b64encode(session_key)
    try:
        keyring.set_password(PROFILE_SESSION_KEYCHAIN_SERVICE, bucket_id, encoded)
        roundtrip = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, bucket_id)
    except KeyringError as exc:
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key write: {exc}") from exc
    except KeyringUnavailableError:
        raise
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly on the profile-session key write: {exc}",
        ) from exc
    if roundtrip != encoded:
        delete_profile_session_key(bucket_id=bucket_id)
        raise KeyringUnavailableError(
            "OS keychain accepted the profile-session key but the round-trip read disagreed; "
            "the backend may be a silent dropper.",
        )


def load_profile_session_key(*, bucket_id: str) -> bytes | None:
    """Fetch the session key for ``bucket_id``, or ``None`` when absent.

    A malformed stored value is deleted best-effort and reported as
    absent, so resume treats it as logged out rather than crashing.

    Args:
        bucket_id: Bucket identifier, canonicalized to form the keychain
            account so two spellings cannot address two entries.

    Returns:
        The 32-byte session key, or ``None`` when no usable entry exists.

    Raises:
        StorageValidationError: When ``bucket_id`` is not a canonical bucket identity.
        KeyringUnavailableError: When the keychain backend is unusable.
    """
    bucket_id = _keychain_bucket_id(bucket_id)
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError as exc:
        raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
    _probe_keychain_backend()
    try:
        stored = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, bucket_id)
    except KeyringError as exc:
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key read: {exc}") from exc
    except KeyringUnavailableError:
        raise
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly on the profile-session key read: {exc}",
        ) from exc
    if stored is None:
        return None
    try:
        key = _b64decode(stored)
    except (ValueError, binascii.Error):
        _log.debug("profile-session keychain entry malformed; deleting bucket_id=%s", bucket_id)
        delete_profile_session_key(bucket_id=bucket_id)
        return None
    if len(key) != _SESSION_KEY_BYTES:
        _log.debug("profile-session keychain entry wrong size; deleting bucket_id=%s", bucket_id)
        delete_profile_session_key(bucket_id=bucket_id)
        return None
    return key


def delete_profile_session_key(*, bucket_id: str) -> None:
    """Delete the keychain session key for ``bucket_id`` (idempotent, best-effort).

    A missing entry is a clean no-op. Backend failures are logged rather
    than raised so logout can never be blocked by keychain state: the
    on-disk record deletion alone already renders a stale keychain key
    useless (split knowledge).

    Args:
        bucket_id: Bucket identifier, canonicalized to form the keychain
            account so two spellings cannot address two entries.

    Raises:
        StorageValidationError: When ``bucket_id`` is not a canonical bucket identity.
    """
    bucket_id = _keychain_bucket_id(bucket_id)
    try:
        import keyring
        from keyring.errors import PasswordDeleteError
    except ImportError:
        return
    try:
        keyring.delete_password(PROFILE_SESSION_KEYCHAIN_SERVICE, bucket_id)
    except PasswordDeleteError:
        return
    except Exception as exc:
        # Deliberately broad: a delete that cannot complete must never block
        # logout, and the backend may raise an OS-level error outside the
        # keyring hierarchy (see the module note on Windows credential
        # errors). The on-disk record deletion alone already renders a stale
        # keychain key useless, so swallowing here loses no security.
        _log.debug(
            "profile-session keychain delete failed bucket_id=%s error_type=%s",
            bucket_id,
            type(exc).__name__,
        )


def profile_session_path(*, storage_root: Path, bucket_id: str) -> Path:
    """Return the ``session.v1.json`` path inside the bucket keystore directory."""
    from ..bucket import keystore_path, validate_keystore_separation

    validate_keystore_separation(storage_root, bucket_id)
    return keystore_path(storage_root, bucket_id) / PROFILE_SESSION_FILENAME


def _document_from_record(record: PersistedProfileSession) -> _PersistedSessionDocument:
    return _PersistedSessionDocument(
        schema_version=record.schema_version,
        bucket_id=record.bucket_id,
        backend_kind=record.backend_kind.value,
        authenticated_at=record.authenticated_at.isoformat(),
        idle_deadline=record.idle_deadline.isoformat(),
        absolute_deadline=record.absolute_deadline.isoformat(),
        nonce_b64=_b64encode(record.nonce),
        ciphertext_b64=_b64encode(record.ciphertext),
        tag_b64=_b64encode(record.tag),
    )


def _record_from_document(document: _PersistedSessionDocument) -> PersistedProfileSession:
    """Hydrate the strict record from an on-disk document.

    Raises:
        ValueError: On any malformed field (base64, datetime, enum, or
            length); the resume evaluation maps this to the ``MALFORMED``
            refusal.
    """
    return PersistedProfileSession(
        schema_version=document.schema_version,
        bucket_id=document.bucket_id,
        backend_kind=SecretStoreBackend(document.backend_kind),
        authenticated_at=validate_utc_aware(datetime.fromisoformat(document.authenticated_at)),
        idle_deadline=validate_utc_aware(datetime.fromisoformat(document.idle_deadline)),
        absolute_deadline=validate_utc_aware(datetime.fromisoformat(document.absolute_deadline)),
        nonce=_b64decode(document.nonce_b64),
        ciphertext=_b64decode(document.ciphertext_b64),
        tag=_b64decode(document.tag_b64),
    )


def write_profile_session(*, storage_root: Path, bucket_id: str, record: PersistedProfileSession) -> None:
    """Atomically persist ``record`` into the bucket keystore directory.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the bucket the record belongs to.
        record: The session record to persist.

    Raises:
        StorageValidationError: When ``record.bucket_id`` does not match
            ``bucket_id``.
    """
    if record.bucket_id != bucket_id:
        raise StorageValidationError(
            f"session record bucket {record.bucket_id!r} does not match target bucket {bucket_id!r}",
        )
    path = profile_session_path(storage_root=storage_root, bucket_id=bucket_id)
    payload = json.dumps(
        _document_from_record(record).model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ).encode(_UTF_8_ENCODING)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_secure_bytes(path, payload + b"\n")


def delete_profile_session(*, storage_root: Path, bucket_id: str) -> None:
    """Delete both persisted session artefacts for ``bucket_id`` (idempotent).

    Removes the on-disk record and the keychain session key. Missing
    artefacts are clean no-ops so logout and fail-closed refusal paths can
    always converge on the logged-out state.
    """
    path = profile_session_path(storage_root=storage_root, bucket_id=bucket_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        _log.debug(
            "profile-session record delete failed path=%s error_type=%s",
            path,
            type(exc).__name__,
        )
    delete_profile_session_key(bucket_id=bucket_id)


def mint_profile_session(
    *,
    storage_root: Path,
    bucket_id: str,
    backend_kind: SecretStoreBackend,
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
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the authenticated bucket.
        backend_kind: The custody backend that authenticated the login.
        dek: The unwrapped 32-byte bucket DEK to session-wrap.
        now: UTC login instant (becomes ``authenticated_at``).
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

    session_key_buffer = bytearray(secrets.token_bytes(_SESSION_KEY_BYTES))
    try:
        record = wrap_profile_session_dek(
            session_key=bytes(session_key_buffer),
            dek=dek,
            bucket_id=bucket_id,
            backend_kind=backend_kind,
            authenticated_at=now,
            idle_deadline=idle_deadline,
            absolute_deadline=absolute_deadline,
        )
        store_profile_session_key(bucket_id=bucket_id, session_key=bytes(session_key_buffer))
        write_profile_session(storage_root=storage_root, bucket_id=bucket_id, record=record)
    finally:
        _zeroise(session_key_buffer)
    return record


def _refusal(
    reason: ProfileSessionRefusalReason,
    record: PersistedProfileSession | None = None,
) -> tuple[ProfileSessionResumeOutcome, None]:
    return ProfileSessionResumeOutcome(resumed=False, refusal=reason, record=record), None


def resume_profile_session(
    *,
    storage_root: Path,
    bucket_id: str,
    now: datetime,
) -> tuple[ProfileSessionResumeOutcome, bytes | None]:
    """Fail-closed evaluation of the persisted session for ``bucket_id``.

    Every refusal branch deletes the stale artefacts before refusing, so
    the next login always starts clean:

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
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the bucket whose session to resume.
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
    path = profile_session_path(storage_root=storage_root, bucket_id=bucket_id)
    if not path.is_file():
        return _refusal(ProfileSessionRefusalReason.ABSENT)

    try:
        document = _PersistedSessionDocument.model_validate_json(path.read_text(encoding=_UTF_8_ENCODING))
        record = _record_from_document(document)
    except (OSError, ValueError, ValidationError):
        _log.debug("profile-session record malformed; deleting bucket_id=%s", bucket_id)
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        return _refusal(ProfileSessionRefusalReason.MALFORMED)

    if record.schema_version != PROFILE_SESSION_SCHEMA_VERSION:
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        return _refusal(ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH)
    if record.bucket_id != bucket_id:
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        return _refusal(ProfileSessionRefusalReason.TAMPERED)
    if now >= record.absolute_deadline:
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        return _refusal(ProfileSessionRefusalReason.EXPIRED_ABSOLUTE, record)
    if now >= record.idle_deadline:
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        return _refusal(ProfileSessionRefusalReason.EXPIRED_IDLE, record)

    session_key = load_profile_session_key(bucket_id=bucket_id)
    if session_key is None:
        with contextlib.suppress(OSError):
            path.unlink()
        return _refusal(ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING, record)

    session_key_buffer = bytearray(session_key)
    del session_key
    try:
        dek = unwrap_profile_session_dek(session_key=bytes(session_key_buffer), record=record)
    except DecryptionError:
        delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
        return _refusal(ProfileSessionRefusalReason.TAMPERED, record)
    finally:
        _zeroise(session_key_buffer)
    return ProfileSessionResumeOutcome(resumed=True, refusal=None, record=record), dek


__all__ = [
    "PROFILE_SESSION_KEYCHAIN_SERVICE",
    "PROFILE_SESSION_SCHEMA_VERSION",
    "PersistedProfileSession",
    "ProfileSessionResumeOutcome",
    "advance_profile_session_idle_deadline",
    "delete_profile_session",
    "delete_profile_session_key",
    "load_profile_session_key",
    "mint_profile_session",
    "profile_session_path",
    "resume_profile_session",
    "store_profile_session_key",
    "unwrap_profile_session_dek",
    "wrap_profile_session_dek",
    "write_profile_session",
]
