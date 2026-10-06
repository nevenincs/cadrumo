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
  custody generation, DEK epoch, the originating-login commitment, the
  sign-in generation, ``issued_at``, the sliding idle deadline,
  and immutable absolute deadline) bound as AEAD associated data.

Every reader decodes a minimal header first and dispatches on its schema
version. Only a current record reaches the strict model; any other version is
a revocable cache from another build, so it is deleted by its header identity
and refused as ``SCHEMA_VERSION_MISMATCH``. A strict parse of an older record
would fail on fields it never had, and that failure must not strand the
receipt or abort a mint that replaces it.

A mint stamps the sign-in generation its caller captured, and writes nothing
unless that generation is still the durable current one. It never creates the
generation record: the runtime establishes it when it publishes the session
the receipt belongs to. The runtime's supplied-key reader verifies the
expected OS login and the current generation, under the custody root lock
that every generation write also holds, before it unwraps the DEK; a receipt
it refuses is deleted there through the typed deletion path. The frontend's
proof borrow reads only the keychain proof and the receipt locator, so no DEK
reaches a frontend and no frontend deletes either half.

A disk-only attacker sees ciphertext no more revealing than the
already-persisted wrapped ``bucket.dek.json``; a keychain-only attacker
holds a random key with nothing to decrypt; altering any persisted
deadline breaks the GCM tag. Resume evaluation is FAIL-CLOSED: an
expired, tampered, version-mismatched, or keychain-orphaned record is
deleted and refused with a typed
:class:`~cadrumo.core.profile_session.ProfileSessionRefusalReason`, never silently
tolerated. No plaintext KEK, DEK, or session-key byte ever lands on disk.

Zeroisation honesty: the session key and DEK are held in ``bytearray``
buffers wiped through :func:`~adapters.persistence.storage.custody.zeroise.zeroise`
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
    :class:`~adapters.persistence.storage.master_key.bucket_session.BucketSession`
        The in-process materialisation this persisted record re-opens.
"""

from __future__ import annotations

import binascii
import json
import secrets
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .....core.base64_codec import b64_decode, b64_encode
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import (
    canonical_json_bytes,
    reject_duplicate_json_members,
    reject_json_constant,
)
from .....core.identity.profile import canonical_profile_bucket_id
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal
from .....core.time.utc import validate_utc_aware
from ..crypto.aes_gcm import KEY_SIZE
from ..errors import (
    DecryptionError,
    KeyringUnavailableError,
    StorageError,
    StorageValidationError,
)
from ..storage_path_definitions import PROFILE_SESSION_FILENAME, PROFILE_SESSION_RETIREMENT_FILENAME
from . import acceleration_receipt_crypto as _crypto
from .acceleration_receipt_crypto import encryption_error
from .errors import ProfileCustodyRecordError
from .filesystem import (
    compare_and_clear_profile_custody_local_record,
    compare_and_replace_profile_custody_local_record,
    profile_custody_local_lock,
    profile_custody_root_lock,
    read_optional_profile_custody_local_record,
)
from .filesystem_primitives import ensure_profile_custody_local_directory
from .sign_in_generation import (
    SignInGeneration,
    SignInGenerationCustody,
    SignInGenerationObservation,
    SignInGenerationState,
)
from .zeroise import zeroise as _zeroise

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

PROFILE_SESSION_RECORD_MAX_BYTES: Final[int] = 8 * 1024
"""Strict ceiling for one canonical ``session.v2.json`` receipt."""

_PROFILE_SESSION_RETIREMENT_MAX_BYTES: Final[int] = 24 * 1024
_PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION: Final[int] = 1


class _AccelerationReceiptDocument(BaseModel):
    """On-disk JSON envelope for one persisted profile session."""

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID
    custody_generation: int = Field(ge=1)
    dek_epoch: str = Field(min_length=1, max_length=128)
    login_binding: _crypto.LoginBindingDigest
    sign_in_lineage: UUID
    sign_in_generation: int = Field(ge=1)
    issued_at: str = Field(min_length=1)
    idle_deadline: str = Field(min_length=1)
    absolute_deadline: str = Field(min_length=1)
    nonce_b64: str = Field(min_length=1)
    ciphertext_b64: str = Field(min_length=1)
    tag_b64: str = Field(min_length=1)


class _ReceiptHeader(BaseModel):
    """The identity every receipt schema shares, read before the strict parse.

    It ignores the remaining fields on purpose: a record from another build
    must still yield the profile and session that name its keychain half, so
    the delete-only path can retire both halves.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="ignore")

    schema_version: int = Field(ge=1)
    profile_id: UUID
    session_id: UUID


type _DecodedReceipt = _crypto.PersistedProfileSession | _ReceiptHeader
"""A current record, or only the header of a record from another schema."""


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


class ReceiptDeletion(StrEnum):
    """What a refused receipt's deletion achieved; never silently assumed."""

    NOT_REQUIRED = "not_required"
    """The receipt was bound, or there was nothing to delete."""

    DELETED = "deleted"
    """Both the keychain key and the on-disk receipt are gone."""

    KEYCHAIN_ENTRY_RETAINED = "keychain_entry_retained"
    """The on-disk receipt is gone; its keychain key could not be confirmed removed.

    The orphaned key unwraps nothing once no record names its session.
    """

    RECEIPT_RETAINED = "receipt_retained"
    """The on-disk receipt survived its compare-and-clear."""


class ProfileSessionResumeOutcome(BaseModel):
    """Typed outcome of a fail-closed persisted-session resume evaluation.

    Never carries key material: the resumed DEK travels beside this record
    as a separate return value so no pydantic dump can surface it.
    ``deletion`` reports how far a refusing reader's typed deletion got;
    readers that do not delete leave it ``NOT_REQUIRED``. ``binding`` names
    the sign-in binding a refused receipt failed; its ``refusal`` is then
    ``ABSENT``, because the receipt no longer signs this login in.
    """

    model_config = _STRICT_FROZEN

    resumed: bool
    refusal: ProfileSessionRefusalReason | None = None
    record: _crypto.PersistedProfileSession | None = None
    deletion: ReceiptDeletion = ReceiptDeletion.NOT_REQUIRED
    binding: ReceiptBindingRefusal | None = None


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
    if len(session_key) != _crypto.PROFILE_SESSION_KEY_BYTES:
        raise StorageValidationError(f"session_key must be exactly {_crypto.PROFILE_SESSION_KEY_BYTES} bytes")
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


def _read_acceleration_secret(*, profile_id: UUID, session_id: UUID) -> bytes | None:
    """Read one receipt's session key without changing the keychain.

    Raises:
        KeyringUnavailableError: When the keychain cannot answer.
        ValueError: When the stored entry is not one encoded session key.
    """
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
    except (ValueError, binascii.Error) as exc:
        raise ValueError("profile-session keychain entry is not base64") from exc
    if len(key) != _crypto.PROFILE_SESSION_KEY_BYTES:
        raise ValueError("profile-session keychain entry has the wrong length")
    return key


def _read_keychain_entry_for_deletion(
    keyring: _ProfileSessionKeyring,
    keyring_error: type[BaseException],
    account: str,
    *,
    refusal_detail: str,
    unexpected_detail: str,
) -> str | None:
    """Read one account while preserving the deletion-phase error wording."""
    try:
        return keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except keyring_error as exc:
        raise KeyringUnavailableError(f"OS keychain refused the {refusal_detail}: {exc}") from exc
    except Exception as exc:
        raise KeyringUnavailableError(f"OS keychain raised unexpectedly {unexpected_detail}: {exc}") from exc


def _delete_keychain_entry(
    *,
    profile_id: UUID,
    session_id: UUID,
) -> None:
    """Delete and independently confirm one exact UUID-pair account."""
    keyring, keyring_error, password_delete_error = _keyring()
    account = _keychain_account(profile_id=profile_id, session_id=session_id)
    present = _read_keychain_entry_for_deletion(
        keyring,
        keyring_error,
        account,
        refusal_detail="profile-session key read before deletion",
        unexpected_detail="before profile-session key deletion",
    )
    if present is None:
        return
    try:
        keyring.delete_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except password_delete_error:
        # A concurrent owner may have deleted it after ``present``.  Do
        # not turn that idempotent absence into a false unavailable
        # outcome; only a second exact read decides it.
        confirmed = _read_keychain_entry_for_deletion(
            keyring,
            keyring_error,
            account,
            refusal_detail="profile-session key deletion confirmation",
            unexpected_detail="during profile-session key deletion confirmation",
        )
        if confirmed is None:
            return
        raise KeyringUnavailableError("OS keychain did not confirm profile-session key deletion") from None
    except keyring_error as exc:
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key deletion: {exc}") from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly during profile-session key deletion: {exc}",
        ) from exc
    confirmed = _read_keychain_entry_for_deletion(
        keyring,
        keyring_error,
        account,
        refusal_detail="profile-session key deletion confirmation",
        unexpected_detail="during profile-session key deletion confirmation",
    )
    if confirmed is not None:
        raise KeyringUnavailableError("OS keychain did not confirm profile-session key deletion")


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
        _delete_keychain_entry(profile_id=profile_id, session_id=session_id)
    except Exception as exc:
        if suppress_unavailable:
            _log.debug("profile-session key cleanup deferred error_type=%s", type(exc).__name__)
            return
        if isinstance(exc, KeyringUnavailableError):
            raise
        raise KeyringUnavailableError(f"OS keychain refused the profile-session key deletion: {exc}") from exc


def profile_session_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return the locator consumed exclusively by custody local-record operations."""
    from ..bucket.keystore_paths import keystore_sidecar_path

    return keystore_sidecar_path(
        storage_root=storage_root,
        bucket_id=canonical_profile_bucket_id(profile_id),
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


def _document_from_record(record: _crypto.PersistedProfileSession) -> _AccelerationReceiptDocument:
    return _AccelerationReceiptDocument(
        schema_version=record.schema_version,
        profile_id=record.profile_id,
        session_id=record.session_id,
        custody_generation=record.custody_generation,
        dek_epoch=record.dek_epoch,
        login_binding=record.login_binding,
        sign_in_lineage=record.sign_in.lineage,
        sign_in_generation=record.sign_in.generation,
        issued_at=record.issued_at.isoformat(),
        idle_deadline=record.idle_deadline.isoformat(),
        absolute_deadline=record.absolute_deadline.isoformat(),
        nonce_b64=b64_encode(record.nonce),
        ciphertext_b64=b64_encode(record.ciphertext),
        tag_b64=b64_encode(record.tag),
    )


def _record_from_document(document: _AccelerationReceiptDocument) -> _crypto.PersistedProfileSession:
    """Hydrate the strict record from an on-disk document.

    Raises:
        ValueError: On any malformed field (base64, datetime, enum, or
            length); the resume evaluation maps this to the ``MALFORMED``
            refusal.
    """
    return _crypto.PersistedProfileSession(
        schema_version=document.schema_version,
        profile_id=document.profile_id,
        session_id=document.session_id,
        custody_generation=document.custody_generation,
        dek_epoch=document.dek_epoch,
        login_binding=document.login_binding,
        sign_in=SignInGeneration(lineage=document.sign_in_lineage, generation=document.sign_in_generation),
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


def _parse_json_object(payload: bytes) -> dict[str, object]:
    """Decode one JSON object, refusing duplicate keys and non-finite constants."""
    decoded = payload.decode(_UTF_8_ENCODING)
    parsed = json.loads(
        decoded,
        object_pairs_hook=reject_duplicate_json_members,
        parse_constant=reject_json_constant,
    )
    if not isinstance(parsed, dict):
        raise ValueError("session receipt must be a JSON object")
    return cast(dict[str, object], parsed)


def _parse_canonical_document(payload: bytes, model: type[BaseModel]) -> BaseModel:
    """Decode exact canonical JSON without accepting duplicate-key aliases."""
    _parse_json_object(payload)
    # ``strict`` models deliberately accept their wire UUID/datetime strings
    # only through Pydantic's JSON boundary.  The independent ``json.loads``
    # above owns duplicate/non-finite refusal before this typed decode.
    document = model.model_validate_json(payload)
    if _canonical_document_bytes(document) != payload:
        raise ValueError("session receipt bytes are not canonical")
    return document


def _parse_receipt_header(payload: bytes) -> _ReceiptHeader:
    """Read the schema-independent identity of one canonical receipt."""
    parsed = _parse_json_object(payload)
    if canonical_json_bytes(parsed) != payload:
        raise ValueError("session receipt bytes are not canonical")
    return _ReceiptHeader.model_validate_json(payload)


def _receipt_bytes(record: _crypto.PersistedProfileSession) -> bytes:
    return _canonical_document_bytes(_document_from_record(record))


def _decode_receipt(payload: bytes) -> _DecodedReceipt:
    """Dispatch on the schema version before any strict parse.

    Raises:
        ValueError: When even the header is malformed or non-canonical.
        ValidationError: When a current-schema record fails strict validation.
    """
    header = _parse_receipt_header(payload)
    if header.schema_version != _crypto.PROFILE_SESSION_SCHEMA_VERSION:
        return header
    document = cast(_AccelerationReceiptDocument, _parse_canonical_document(payload, _AccelerationReceiptDocument))
    return _record_from_document(document)


def _current_record(decoded: _DecodedReceipt) -> _crypto.PersistedProfileSession | None:
    return decoded if isinstance(decoded, _crypto.PersistedProfileSession) else None


def _read_receipt(path: Path) -> tuple[bytes, _DecodedReceipt] | None:
    """Read and decode one receipt through the canonical anchored authority."""
    payload = read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
    if payload is None:
        return None
    return payload, _decode_receipt(payload)


def inspect_profile_session(*, storage_root: Path, profile_id: UUID) -> _crypto.PersistedProfileSession | None:
    """Read current receipt metadata without keychain access, mutation or DEK unwrapping.

    Missing parents and superseded schemas have no current receipt. Malformed,
    linked or unreadable records raise so callers preserve an unknown result.
    This observation cannot authenticate the metadata without the separate proof.
    """
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    for parent in (path.parent.parent, path.parent):
        try:
            parent.lstat()
        except FileNotFoundError:
            return None
    captured = _read_receipt(path)
    return None if captured is None else _current_record(captured[1])


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
    record: _crypto.PersistedProfileSession,
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
        prior_record = _decode_receipt(predecessor)
        if prior_record.profile_id != profile_id:
            raise StorageValidationError("profile-session retirement predecessor profile differs")
    successor_record = _decode_receipt(successor)
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
            prior = _decode_receipt(predecessor)
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
        successor_record = _decode_receipt(successor)
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


def _clear_retirement_journal(journal_path: Path, *, payload: bytes) -> bool:
    """Clear one exact retirement journal whose keychain half cannot be retired.

    The journal carries the wrapped DEK of every receipt it names, so it is an
    on-disk half of the session exactly like the receipt. A keychain entry it
    would have retired holds only a random session key that unwraps nothing
    once no on-disk record names its session id, and no later receipt can name
    it because every mint draws a fresh one. Clearing the journal is therefore
    the fail-closed direction: an entry that may exist is left inert, never
    reachable, and never reused.
    """
    cleared = _clear_captured_receipt(
        journal_path,
        payload=payload,
        maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
    )
    if cleared:
        _log.debug("profile-session retirement journal cleared with its keychain half unreachable")
    return cleared


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
    """Complete journalled custody cleanup only after both receipt halves are absent.

    Global human sign-out uses its separate generation-first typed outcome.
    Custody deletion must preserve retry evidence when physical cleanup fails.
    """
    with profile_custody_root_lock(storage_root):
        _delete_profile_session(storage_root=storage_root, profile_id=profile_id)


def revoke_profile_sign_in(sign_in: SignInGenerationCustody) -> ReceiptDeletion:
    """Durably fence all issued receipts before attempting their bounded deletion.

    The runtime holds its admission guard across this call and retirement of
    live human sessions. A failed generation write raises before any deletion;
    failure to remove either receipt half is returned explicitly.
    """
    with profile_custody_root_lock(sign_in.root):
        sign_in.advance()
        path = profile_session_path(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
        try:
            _ensure_profile_session_directory(path)
            with profile_custody_local_lock(_profile_session_lock_path(path)):
                keychain_retained = False
                try:
                    _recover_pending_retirement(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
                except (KeyringUnavailableError, ProfileCustodyRecordError, StorageValidationError):
                    keychain_retained = True
                _clear_unrecovered_retirement(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
                captured = _read_receipt(path)
                if captured is None:
                    return (
                        ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED if keychain_retained else ReceiptDeletion.NOT_REQUIRED
                    )
                payload, record = captured
                if record.profile_id != sign_in.binding.profile_id:
                    return ReceiptDeletion.RECEIPT_RETAINED
                deletion = _delete_refused_receipt(path=path, payload=payload, decoded=record)
                if keychain_retained and deletion is ReceiptDeletion.DELETED:
                    return ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED
                return deletion
        except (OSError, ValueError, StorageError, ProfileCustodyRecordError):
            return ReceiptDeletion.RECEIPT_RETAINED


def _delete_profile_session(*, storage_root: Path, profile_id: UUID) -> None:
    """Retain the exact key locator until confirmed keychain and receipt removal."""
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    _ensure_profile_session_directory(path)
    with profile_custody_local_lock(_profile_session_lock_path(path)):
        # A failed recovery leaves its journal available for the next custody
        # attempt. Discarding it would lose the only locator of an orphan key.
        _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
        observed = _read_receipt(path)
        if observed is None:
            return
        payload, record = observed
        if record.profile_id != profile_id:
            raise AccelerationReceiptRevocationError(
                translated_message="errors.fail.fail_acceleration_receipt_revocation",
                context={"profile_id": canonical_profile_bucket_id(profile_id)},
            )
        _delete_acceleration_secret(
            profile_id=record.profile_id,
            session_id=record.session_id,
            suppress_unavailable=False,
        )
        if not _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES):
            raise AccelerationReceiptRevocationError(
                translated_message="errors.fail.fail_acceleration_receipt_revocation",
                context={"profile_id": canonical_profile_bucket_id(profile_id)},
            )


def _clear_unrecovered_retirement(*, storage_root: Path, profile_id: UUID) -> None:
    """Remove a retirement journal that recovery could not consume.

    Revocation is the strong close: it removes every on-disk half whether or
    not the keychain answers, as it already does for the receipt itself.

    Raises:
        AccelerationReceiptRevocationError: The journal survived its clear.
    """
    journal_path = _profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    payload = read_optional_profile_custody_local_record(
        journal_path,
        maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
    )
    if payload is None:
        return
    if not _clear_retirement_journal(journal_path, payload=payload):
        raise AccelerationReceiptRevocationError(
            translated_message="errors.fail.fail_acceleration_receipt_revocation",
            context={"profile_id": canonical_profile_bucket_id(profile_id)},
        )


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
    login_id: str,
    sign_in: SignInGenerationCustody,
    generation: SignInGeneration,
) -> _crypto.PersistedProfileSession:
    """Mint a profile receipt under the custody-wide session lifecycle lock.

    Validate all deterministic receipt inputs before opening the custody root.
    A rejected bootstrap call must not provision a durable lock leaf merely
    to report malformed identity, metadata, key material, or time windows.

    The receipt binds ``login_id``, the originating OS login, and exactly
    ``generation``: the value the caller captured from ``sign_in`` when it
    published the session, never a fresh read. Under the custody root lock,
    which every generation write also holds, the mint refuses before any
    keychain or receipt write unless ``generation`` is still current. A
    sign-out or lock-down that advanced it in between therefore leaves no
    receipt, and a missing record is never created here.

    Raises:
        StorageValidationError: When an input is malformed or ``sign_in`` is
            bound to another storage root, profile or custody generation.
        AutomationCustodyError: ``INVALID`` when ``sign_in`` is not the
            committed custody; ``CONFLICT`` when ``generation`` is no longer
            current.
        ProfileCustodyRecordError: When the custody root lock cannot be held.
    """
    if idle_minutes <= 0:
        raise StorageValidationError("idle_minutes must be a strict positive integer")
    if absolute_minutes <= 0:
        raise StorageValidationError("absolute_minutes must be a strict positive integer")
    if len(dek) != KEY_SIZE:
        raise encryption_error(f"dek must be exactly {KEY_SIZE} bytes")
    now = _crypto.validate_profile_session_metadata(
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        issued_at=now,
    )
    if not login_id or len(login_id) > _crypto.PROFILE_SESSION_LOGIN_ID_MAX_LENGTH:
        raise StorageValidationError("login_id must be a non-empty OS login locator of bounded length")
    if (
        sign_in.root != storage_root
        or sign_in.binding.profile_id != profile_id
        or sign_in.binding.custody_generation != custody_generation
    ):
        raise StorageValidationError("sign-in generation custody does not belong to this receipt")
    with profile_custody_root_lock(storage_root):
        sign_in.require_current(generation)
        return _mint_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            dek=dek,
            now=now,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
            login_id=login_id,
            sign_in=generation,
        )


def _mint_profile_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    dek: bytes,
    now: datetime,
    idle_minutes: int,
    absolute_minutes: int,
    login_id: str,
    sign_in: SignInGeneration,
) -> _crypto.PersistedProfileSession:
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
        login_id: Originating OS login, bound only as a salted commitment.
        sign_in: The durable sign-in generation the receipt is stamped with.

    Returns:
        The persisted :class:`~.acceleration_receipt_crypto.PersistedProfileSession`.

    Raises:
        StorageValidationError: On non-positive windows.
        EncryptionError: On wrap failure.
        KeyringUnavailableError: When the OS keychain cannot custody the
            session key.
    """
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

        session_key_buffer = bytearray(secrets.token_bytes(_crypto.PROFILE_SESSION_KEY_BYTES))
        session_id = uuid4()
        try:
            record = _crypto.wrap_profile_session_dek(
                session_key=bytes(session_key_buffer),
                dek=dek,
                profile_id=profile_id,
                session_id=session_id,
                custody_generation=custody_generation,
                dek_epoch=dek_epoch,
                login_id=login_id,
                sign_in=sign_in,
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
    record: _crypto.PersistedProfileSession | None = None,
    *,
    deletion: ReceiptDeletion = ReceiptDeletion.NOT_REQUIRED,
    binding: ReceiptBindingRefusal | None = None,
) -> tuple[ProfileSessionResumeOutcome, None]:
    outcome = ProfileSessionResumeOutcome(
        resumed=False, refusal=reason, record=record, deletion=deletion, binding=binding
    )
    return outcome, None


def _resume_artifacts_present(*, path: Path, retirement_path: Path) -> bool:
    """Observe whether either receipt artifact exists without taking a lock."""
    if (
        read_optional_profile_custody_local_record(
            path,
            maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
        )
        is not None
    ):
        return True
    return (
        read_optional_profile_custody_local_record(
            retirement_path,
            maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
        )
        is not None
    )


def _receipt_refusal_reason(
    *,
    record: _crypto.PersistedProfileSession,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
) -> ProfileSessionRefusalReason | None:
    """Classify current metadata without choosing a caller's cleanup policy."""
    if record.schema_version != _crypto.PROFILE_SESSION_SCHEMA_VERSION:
        return ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH
    if record.profile_id != profile_id:
        return ProfileSessionRefusalReason.TAMPERED
    if record.custody_generation != custody_generation or record.dek_epoch != dek_epoch:
        return ProfileSessionRefusalReason.CUSTODY_CHANGED
    if now >= record.absolute_deadline:
        return ProfileSessionRefusalReason.EXPIRED_ABSOLUTE
    if now >= record.idle_deadline:
        return ProfileSessionRefusalReason.EXPIRED_IDLE
    return None


def borrow_profile_session_key(
    *,
    storage_root: Path,
    profile_id: UUID,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Read only the keychain proof that the receipt's locator names.

    This is the frontend's whole share of a receipt: it reads the receipt's
    schema-independent header for the session the keychain account is named
    by, then reads that account. It never decrypts the record, unwraps the DEK,
    evaluates deadlines or custody, settles a retirement journal, or deletes
    either half; the runtime's supplied-key reader decides and owns every
    deletion. A ``resumed`` outcome here means only that a proof was read; it
    carries no record. The returned buffer belongs to its caller, which must
    wipe it after one protected IPC exchange.

    The receipt-local lock is held only so the locator and key are read as a
    pair against a concurrent mint or deletion; nothing is written under it.
    """
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    if not path.parent.is_dir():
        # A profile that never held a receipt has no keystore directory; the
        # borrow reports that without provisioning one.
        return _refusal(ProfileSessionRefusalReason.ABSENT)
    try:
        if read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES) is None:
            return _refusal(ProfileSessionRefusalReason.ABSENT)
        with profile_custody_local_lock(_profile_session_lock_path(path)):
            payload = read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
            if payload is None:
                return _refusal(ProfileSessionRefusalReason.ABSENT)
            locator = _parse_receipt_header(payload)
            if locator.profile_id != profile_id:
                return _refusal(ProfileSessionRefusalReason.TAMPERED)
            try:
                key = _read_acceleration_secret(profile_id=locator.profile_id, session_id=locator.session_id)
            except KeyringUnavailableError:
                return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE)
            if key is None:
                return _refusal(ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING)
            return ProfileSessionResumeOutcome(resumed=True), bytearray(key)
    except (ProfileCustodyRecordError, StorageValidationError, ValueError, ValidationError):
        return _refusal(ProfileSessionRefusalReason.MALFORMED)


def resume_profile_session_with_key(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
    receipt_key: bytearray,
    login_id: str,
    sign_in: SignInGenerationCustody,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Verify a supplied human wrap key; the runtime's only receipt unwrap.

    It never reads the keychain for a key. Before any unwrap it checks the
    receipt against ``login_id``, the originating OS login of the connection
    presenting the proof, and against the generation ``sign_in`` currently
    holds, observed under the custody root lock that every generation write
    also holds. A receipt that its own bytes refuse whatever proof is
    supplied -- malformed, another schema, another profile, changed custody,
    an elapsed deadline, another login, or a generation that is missing,
    unreadable or no longer current -- is deleted here, both halves, and the
    outcome reports how far that deletion got. A wrong client proof never
    deletes the current record or its stored key, because a proof that fails
    to unwrap cannot tell a stale or forged key from a corrupt record. The
    verified record carries the original deadlines; this door does not
    advance either deadline or publish an ambient process session.

    Raises:
        StorageValidationError: When ``sign_in`` is bound to another storage
            root or profile than the receipt being resumed.
    """
    now = validate_utc_aware(now)
    if sign_in.root != storage_root or sign_in.binding.profile_id != profile_id:
        raise StorageValidationError("sign-in generation custody does not belong to this receipt")
    if len(receipt_key) != _crypto.PROFILE_SESSION_KEY_BYTES:
        return _refusal(ProfileSessionRefusalReason.TAMPERED)
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    retirement_path = _profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    try:
        with profile_custody_root_lock(storage_root):
            _ensure_profile_session_directory(path)
            if not _resume_artifacts_present(path=path, retirement_path=retirement_path):
                return _refusal(ProfileSessionRefusalReason.ABSENT)
            with profile_custody_local_lock(_profile_session_lock_path(path)):
                # An interrupted key swap is settled here, by the runtime, as
                # an exact-byte decision on the journal; the supplied key never
                # chooses a side. A keychain that cannot answer leaves it pending.
                try:
                    _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
                except KeyringUnavailableError:
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE)
                payload = read_optional_profile_custody_local_record(
                    path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES
                )
                if payload is None:
                    return _refusal(ProfileSessionRefusalReason.ABSENT)
                return _resume_supplied_key_locked(
                    path=path,
                    payload=payload,
                    expected=_ExpectedReceipt(
                        profile_id=profile_id,
                        custody_generation=custody_generation,
                        dek_epoch=dek_epoch,
                        now=now,
                        login_id=login_id,
                        generation=sign_in.observe(),
                    ),
                    receipt_key=receipt_key,
                )
    except (ProfileCustodyRecordError, StorageValidationError, ValueError, ValidationError):
        return _refusal(ProfileSessionRefusalReason.MALFORMED)


class _ExpectedReceipt(BaseModel):
    """Everything a receipt must match before its supplied key may unwrap it."""

    model_config = _STRICT_FROZEN

    profile_id: UUID
    custody_generation: int
    dek_epoch: str
    now: datetime
    login_id: str
    generation: SignInGenerationObservation


_GENERATION_UNAVAILABLE: Final[dict[SignInGenerationState, ReceiptBindingRefusal]] = {
    SignInGenerationState.MISSING: ReceiptBindingRefusal.GENERATION_MISSING,
    SignInGenerationState.UNREADABLE: ReceiptBindingRefusal.GENERATION_UNREADABLE,
    SignInGenerationState.BINDING_MISMATCH: ReceiptBindingRefusal.GENERATION_BINDING_MISMATCH,
}


def _receipt_binding_refusal(
    *, record: _crypto.PersistedProfileSession, login_id: str, generation: SignInGenerationObservation
) -> ReceiptBindingRefusal | None:
    """Decide whether ``record`` belongs to the expected sign-in, with no I/O.

    The generation fence is checked before the login: it is the revocation
    authority, and a fenced receipt is refused whichever login it names.
    """
    if generation.current is None:
        return _GENERATION_UNAVAILABLE.get(generation.state, ReceiptBindingRefusal.GENERATION_UNREADABLE)
    if record.sign_in != generation.current:
        return ReceiptBindingRefusal.GENERATION_CHANGED
    if not _crypto.profile_session_login_matches(record=record, login_id=login_id):
        return ReceiptBindingRefusal.LOGIN_MISMATCH
    return None


def _refuse_supplied_key_receipt(
    reason: ProfileSessionRefusalReason,
    *,
    path: Path,
    payload: bytes,
    decoded: _DecodedReceipt,
    binding: ReceiptBindingRefusal | None = None,
) -> tuple[ProfileSessionResumeOutcome, None]:
    """Delete a receipt its own bytes refuse, and report the deletion it achieved."""
    deletion = _delete_refused_receipt(path=path, payload=payload, decoded=decoded)
    if deletion is not ReceiptDeletion.DELETED:
        _log.warning(
            "refused profile-session receipt not fully deleted reason=%s binding=%s deletion=%s",
            reason.value,
            None if binding is None else binding.value,
            deletion.value,
        )
    return _refusal(reason, _current_record(decoded), deletion=deletion, binding=binding)


def _resume_supplied_key_locked(
    *,
    path: Path,
    payload: bytes,
    expected: _ExpectedReceipt,
    receipt_key: bytearray,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Decide one captured receipt against a supplied key under both receipt locks."""
    try:
        decoded = _decode_receipt(payload)
    except (ValueError, ValidationError):
        cleared = _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
        return _refusal(
            ProfileSessionRefusalReason.MALFORMED,
            deletion=ReceiptDeletion.DELETED if cleared else ReceiptDeletion.RECEIPT_RETAINED,
        )
    record = _current_record(decoded)
    if record is None:
        return _refuse_supplied_key_receipt(
            ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH, path=path, payload=payload, decoded=decoded
        )
    reason = _receipt_refusal_reason(
        record=record,
        profile_id=expected.profile_id,
        custody_generation=expected.custody_generation,
        dek_epoch=expected.dek_epoch,
        now=expected.now,
    )
    if reason is not None:
        return _refuse_supplied_key_receipt(reason, path=path, payload=payload, decoded=decoded)
    binding = _receipt_binding_refusal(record=record, login_id=expected.login_id, generation=expected.generation)
    if binding is not None:
        return _refuse_supplied_key_receipt(
            ProfileSessionRefusalReason.ABSENT, path=path, payload=payload, decoded=decoded, binding=binding
        )
    try:
        dek = _crypto.unwrap_profile_session_dek(session_key=bytes(receipt_key), record=record)
    except DecryptionError:
        return _refusal(ProfileSessionRefusalReason.TAMPERED, record)
    return ProfileSessionResumeOutcome(resumed=True, record=record), dek


def _delete_refused_receipt(*, path: Path, payload: bytes, decoded: _DecodedReceipt) -> ReceiptDeletion:
    """Remove both halves of a refused receipt and report what remains.

    The disk half is cleared even when the keychain cannot answer, as
    revocation does: a key with no record naming its session unwraps nothing.
    """
    keychain_retained = False
    try:
        _delete_acceleration_secret(
            profile_id=decoded.profile_id,
            session_id=decoded.session_id,
            suppress_unavailable=False,
        )
    except KeyringUnavailableError:
        keychain_retained = True
    if not _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES):
        return ReceiptDeletion.RECEIPT_RETAINED
    return ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED if keychain_retained else ReceiptDeletion.DELETED


__all__ = [
    "PROFILE_SESSION_KEYCHAIN_SERVICE",
    "ProfileSessionResumeOutcome",
    "ReceiptBindingRefusal",
    "ReceiptDeletion",
    "borrow_profile_session_key",
    "delete_profile_session",
    "mint_profile_session",
    "profile_session_path",
    "resume_profile_session_with_key",
]
